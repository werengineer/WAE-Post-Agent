#!/usr/bin/env bash
# Sets up the OpenWA WhatsApp gateway (unofficial: you link a number by scanning a QR code) on the same Ubuntu server as the agent.
# Run it BEFORE deploy/install.sh when you choose OpenWA. Needs sudo and a real terminal.
#
#   bash deploy/openwa-setup.sh
#
# What it does: installs Docker if missing, fetches OpenWA (github.com/rmyndharis/OpenWA) into /opt/openwa, starts it on 127.0.0.1:2785 only,
# makes a session called "wae-leads", registers the webhook to the agent and saves the connection values in /opt/openwa/.wae-openwa.env
# (read by install.sh, so nothing has to be typed twice). Then it tells you how to scan the QR code.
# Safe to run again.
#
# Honest warnings: OpenWA is NOT an official WhatsApp product (the number can be restricted or banned), it runs a Chromium browser
# (about 1 GB of memory) and a Docker image (a few GB of disk). On a small server that also runs other services, check the numbers shown below.
set -euo pipefail

OPENWA_DIR=/opt/openwa
OPENWA_REPO=https://github.com/rmyndharis/OpenWA.git
SESSION_NAME=${SESSION_NAME:-wae-leads}
API=http://127.0.0.1:2785/api
ENV_OUT="$OPENWA_DIR/.wae-openwa.env"

say() { printf '\n== %s\n' "$*"; }
die() { printf '\nSTOP: %s\n' "$*" >&2; exit 1; }
[ -t 0 ] || die "Run this in an interactive terminal."
command -v sudo >/dev/null || die "sudo is needed."
command -v apt-get >/dev/null || die "This script is for Ubuntu/Debian (apt)."

say "1/6 Is there room? (memory and disk)"
MEM_FREE=$(free -m | awk '/^Mem:/ {print $7}')
DISK_FREE=$(df -Pm /opt | awk 'NR==2 {print $4}')
echo "available memory: ${MEM_FREE} MB (OpenWA wants about 1000 MB)    free disk: ${DISK_FREE} MB (it wants about 6000 MB)"
if [ "${MEM_FREE:-0}" -lt 1200 ] || [ "${DISK_FREE:-0}" -lt 6000 ]; then
  echo "This server is tight. OpenWA could slow down or even stop the services that run here (the WAE Bot)."
  echo "A separate small server for the agent and OpenWA is the safer choice."
  read -rp "Continue anyway? Type yes to go on: " GO </dev/tty
  [ "$GO" = yes ] || die "Stopped. Nothing was installed."
fi

say "2/6 Docker"
if ! command -v docker >/dev/null; then
  sudo apt-get update -y
  sudo apt-get install -y docker.io curl git openssl
fi
if ! sudo docker compose version >/dev/null 2>&1; then
  sudo apt-get install -y docker-compose-v2 || true
fi
sudo docker compose version >/dev/null 2>&1 || die "Docker Compose is missing. Install the 'docker-compose-v2' (or docker-compose-plugin) package and run this again."
sudo systemctl enable --now docker >/dev/null 2>&1 || true

say "3/6 OpenWA code in $OPENWA_DIR"
if [ -d "$OPENWA_DIR/.git" ]; then
  sudo git -C "$OPENWA_DIR" pull --ff-only
else
  sudo git clone "$OPENWA_REPO" "$OPENWA_DIR"
fi
# the agent runs on the host (port 8000): OpenWA, inside Docker, must be allowed to call it by the name host.docker.internal
sudo tee "$OPENWA_DIR/docker-compose.wae.yml" >/dev/null <<'EOF'
services:
  openwa:
    environment:
      SSRF_ALLOWED_HOSTS: host.docker.internal
    extra_hosts:
      - "host.docker.internal:host-gateway"
EOF

say "4/6 Starting OpenWA (the first build can take several minutes)"
(cd "$OPENWA_DIR" && sudo docker compose -f docker-compose.dev.yml -f docker-compose.wae.yml up -d --build)
printf 'waiting for OpenWA'
for _ in $(seq 1 90); do
  if curl -fsS -o /dev/null "http://127.0.0.1:2785/api/health/ready" 2>/dev/null; then READY=1; break; fi
  printf '.'; sleep 2
done
echo
[ "${READY:-0}" = 1 ] || { sudo docker logs --tail 40 openwa-api || true; die "OpenWA did not become ready (log above)."; }

say "5/6 Session and webhook"
KEY=$(sudo docker exec openwa-api cat /app/data/.api-key 2>/dev/null | tr -d '[:space:]') || true
[ -n "$KEY" ] || die "Could not read OpenWA's API key (docker exec openwa-api cat /app/data/.api-key)."

json_id() { python3 -c 'import json,sys
try:
    d=json.load(sys.stdin)
except Exception:
    sys.exit(0)
d=d.get("data",d) if isinstance(d,dict) else d
if isinstance(d,dict): print(d.get("id",""))'; }
find_session() { python3 -c 'import json,sys
name=sys.argv[1]
try:
    d=json.load(sys.stdin)
except Exception:
    sys.exit(0)
d=d.get("data",d) if isinstance(d,dict) else d
for s in (d if isinstance(d,list) else []):
    if isinstance(s,dict) and s.get("name")==name:
        print(s.get("id","")); break' "$SESSION_NAME"; }

SESSION_ID=$(curl -fsS -H "X-API-Key: $KEY" "$API/sessions" | find_session || true)
if [ -z "$SESSION_ID" ]; then
  SESSION_ID=$(curl -fsS -X POST -H "X-API-Key: $KEY" -H "Content-Type: application/json" -d "{\"name\":\"$SESSION_NAME\"}" "$API/sessions" | json_id || true)
fi
[ -n "$SESSION_ID" ] || die "Could not create or find the session '$SESSION_NAME'. Open the OpenWA dashboard and create it by hand, then write its id in $ENV_OUT."
echo "session '$SESSION_NAME' = $SESSION_ID"

WEBHOOK_SECRET=""
if sudo test -f "$ENV_OUT"; then
  WEBHOOK_SECRET=$(sudo awk -F= '$1=="OPENWA_WEBHOOK_SECRET"{print $2; exit}' "$ENV_OUT")
fi
if [ -z "$WEBHOOK_SECRET" ]; then
  WEBHOOK_SECRET=$(openssl rand -hex 24)
  CODE=$(curl -sS -o /tmp/openwa-webhook.out -w '%{http_code}' -X POST -H "X-API-Key: $KEY" -H "Content-Type: application/json" \
    -d "{\"url\":\"http://host.docker.internal:8000/openwa/webhook\",\"events\":[\"message.received\"],\"secret\":\"$WEBHOOK_SECRET\"}" \
    "$API/sessions/$SESSION_ID/webhooks")
  if [ "$CODE" != 200 ] && [ "$CODE" != 201 ]; then
    cat /tmp/openwa-webhook.out; rm -f /tmp/openwa-webhook.out
    die "OpenWA refused the webhook (HTTP $CODE, answer above). Nothing was saved; fix it and run this script again."
  fi
  rm -f /tmp/openwa-webhook.out
  echo "webhook registered"
else
  echo "webhook was registered before: kept"
fi

TMP=$(mktemp); chmod 600 "$TMP"
printf 'OPENWA_BASE_URL=http://127.0.0.1:2785\nOPENWA_API_KEY=%s\nOPENWA_SESSION_ID=%s\nOPENWA_WEBHOOK_SECRET=%s\n' "$KEY" "$SESSION_ID" "$WEBHOOK_SECRET" >"$TMP"
sudo install -o root -g root -m 600 "$TMP" "$ENV_OUT"; rm -f "$TMP"
unset KEY WEBHOOK_SECRET
echo "saved $ENV_OUT (mode 600)"

say "6/6 Start the session and scan the QR code"
# start it so that the QR code appears (it is fine if it is already running)
curl -sS -o /dev/null -X POST -H "X-API-Key: $(sudo awk -F= '$1=="OPENWA_API_KEY"{print $2; exit}' "$ENV_OUT")" "$API/sessions/$SESSION_ID/start" || true
cat <<EOF

The OpenWA dashboard listens on this server's localhost only (port 2785 is NOT open to the internet, and must stay closed).
To reach it from your laptop, open a second PowerShell on your laptop and run:

    ssh -i "C:\\Users\\ayush\\Downloads\\wae-bot-key.pem" -L 2785:127.0.0.1:2785 ubuntu@34.199.13.214

Leave that window open, then in your browser go to  http://localhost:2785
(if it asks for the API key:  sudo grep OPENWA_API_KEY $ENV_OUT ). Open the session "$SESSION_NAME", press Start,
and scan the QR code with the phone that has the business number: WhatsApp > Linked devices > Link a device.
When the session shows as connected, come back here and run:   bash deploy/install.sh   (choose 1 = OpenWA)

EOF
