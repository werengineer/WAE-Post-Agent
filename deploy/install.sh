#!/usr/bin/env bash
# Installs the WAE Post Agent next to the WAE Bot on its EC2 server (Ubuntu 22.04 / 24.04) and links the two.
# Run it as a user that has sudo, in a real terminal (it asks for the secrets; nothing secret is on the command line):
#
#   bash deploy/install.sh        (or, first time:  curl -fsSL https://raw.githubusercontent.com/werengineer/WAE-Post-Agent/main/deploy/install.sh -o install.sh && bash install.sh)
#
# It is safe to run again: an existing .env is kept, existing /etc/wae-bot.env keys are never overwritten, the code is updated with a fast-forward pull.
# What it does NOT do: edit nginx and talk to Meta (the two manual steps are printed at the end), restart the WAE Bot (do that after copying its new code).
set -euo pipefail

APP_DIR=/opt/wae-post-agent
APP_USER=${APP_USER:-wae}
REPO=https://github.com/werengineer/WAE-Post-Agent.git
BRANCH=${BRANCH:-main}   # BRANCH=<name> bash install.sh installs from another branch (until it is merged)
BOT_ENV=/etc/wae-bot.env

say() { printf '\n== %s\n' "$*"; }
die() { printf '\nSTOP: %s\n' "$*" >&2; exit 1; }
[ -t 0 ] || die "Run this in an interactive terminal (it asks for the secrets)."
command -v sudo >/dev/null || die "sudo is needed."
id "$APP_USER" >/dev/null 2>&1 || die "User '$APP_USER' does not exist (the WAE Bot's user). Set APP_USER=<name> if it is called something else."
[ -f "$BOT_ENV" ] || die "$BOT_ENV not found: is this the WAE Bot server?"

# value of KEY in an env file (read as root, printed to the caller only; never echoed by this script)
envval() { sudo awk -F= -v k="$2" '$1==k { sub(/^[^=]*=/, ""); gsub(/^"|"$/, ""); print; exit }' "$1" 2>/dev/null || true; }
ask() { # ask VAR "prompt" [secret]
  local __v
  if [ "${3:-}" = secret ]; then read -rsp "$2: " __v </dev/tty; echo; else read -rp "$2: " __v </dev/tty; fi
  printf -v "$1" '%s' "$__v"
}
digits() { [[ "$1" =~ ^[0-9]{10,15}$ ]]; }

say "1/7 Python 3.11+"
PY=""
for c in python3.12 python3.11 python3; do
  if command -v "$c" >/dev/null && "$c" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)'; then PY=$c; break; fi
done
if [ -z "$PY" ]; then
  sudo apt-get update -y
  sudo apt-get install -y software-properties-common
  sudo add-apt-repository -y ppa:deadsnakes/python
  sudo apt-get update -y
  sudo apt-get install -y python3.11 python3.11-venv
  PY=python3.11
fi
sudo apt-get install -y git openssl "${PY}-venv" >/dev/null 2>&1 || sudo apt-get install -y git openssl python3-venv
echo "using $PY ($($PY --version))"

say "2/7 Code in $APP_DIR"
if [ -d "$APP_DIR/.git" ]; then
  sudo -u "$APP_USER" git -C "$APP_DIR" fetch origin "$BRANCH"
  sudo -u "$APP_USER" git -C "$APP_DIR" checkout "$BRANCH"
  sudo -u "$APP_USER" git -C "$APP_DIR" pull --ff-only origin "$BRANCH"
else
  sudo mkdir -p "$APP_DIR" && sudo chown "$APP_USER:$APP_USER" "$APP_DIR"
  sudo -u "$APP_USER" git clone -b "$BRANCH" "$REPO" "$APP_DIR"
fi

say "3/7 Virtual environment and tests"
[ -d "$APP_DIR/.venv" ] || sudo -u "$APP_USER" "$PY" -m venv "$APP_DIR/.venv"
sudo -u "$APP_USER" "$APP_DIR/.venv/bin/python" -m pip install -q -r "$APP_DIR/requirements.txt" -r "$APP_DIR/requirements-dev.txt"
(cd "$APP_DIR" && sudo -u "$APP_USER" .venv/bin/python -m unittest discover -s tests) || die "The tests failed. Send the output above; nothing was started."

say "4/7 Settings (.env)"
if sudo test -f "$APP_DIR/.env"; then
  echo "$APP_DIR/.env already exists: kept as it is."
else
  ask GROQ_KEY "Groq API key (typing is hidden)" secret
  [ -n "$GROQ_KEY" ] || die "The Groq key is empty."
  ask APP_SECRET "Meta app secret (Meta app > Settings > Basic; typing is hidden)" secret
  [ -n "$APP_SECRET" ] || die "The Meta app secret is empty."
  ask CUSTOMER "Customer chat the agent may read and answer (digits only, country code first, e.g. 919876543210)"
  digits "$CUSTOMER" || die "That is not a phone number in digits."
  ask OWNER "Number that gets the 'new lead / draft ready' notifications (digits only)"
  digits "$OWNER" || die "That is not a phone number in digits."

  PHONE_ID=$(envval "$BOT_ENV" WHATSAPP_PHONENUM_ID)
  TOKEN=$(envval "$BOT_ENV" WHATSAPP_PERMANENT_TOKEN)
  ask SAME "Use the same business number as the WAE Bot (its id ends ...${PHONE_ID: -4})? [Y/n]"
  if [[ "$SAME" =~ ^[Nn] ]]; then
    ask PHONE_ID "Phone number id of the other number (Meta > WhatsApp > API setup)"
    ask TOKEN "Access token for it (typing is hidden)" secret
  fi
  [ -n "$PHONE_ID" ] && [ -n "$TOKEN" ] || die "No WhatsApp phone number id / token (looked in $BOT_ENV)."

  VERIFY=$(openssl rand -hex 24); API_TOKEN=$(openssl rand -hex 24); SOCIAL_TOKEN=$(openssl rand -hex 24)
  TMP=$(mktemp); trap 'rm -f "$TMP"' EXIT; chmod 600 "$TMP"
  cat >"$TMP" <<EOF
GROQ_API_KEY=$GROQ_KEY
GROQ_MODEL=openai/gpt-oss-120b
AGENT_TIMEZONE=Asia/Kolkata
WHATSAPP_PROVIDER=cloud
WHATSAPP_PHONE_NUMBER_ID=$PHONE_ID
WHATSAPP_ACCESS_TOKEN=$TOKEN
WHATSAPP_APP_SECRET=$APP_SECRET
WHATSAPP_VERIFY_TOKEN=$VERIFY
OPENWA_TEST_CHAT_ID=${CUSTOMER}@c.us
OPENWA_OWNER_CHAT_ID=${OWNER}@c.us
OPENWA_ALLOW_ALL_CHATS=false
WHATSAPP_DB=whatsapp.sqlite3
WHATSAPP_API_TOKEN=$API_TOKEN
WHATSAPP_API_ORIGINS=
SOCIAL_WEBHOOK_URL=https://ai.wae.company/inbox/social
SOCIAL_WEBHOOK_TOKEN=$SOCIAL_TOKEN
EOF
  sudo install -o "$APP_USER" -g "$APP_USER" -m 600 "$TMP" "$APP_DIR/.env"
  rm -f "$TMP"; trap - EXIT
  unset GROQ_KEY APP_SECRET TOKEN
  echo "created $APP_DIR/.env (mode 600)"
fi
API_TOKEN=$(envval "$APP_DIR/.env" WHATSAPP_API_TOKEN)
SOCIAL_TOKEN=$(envval "$APP_DIR/.env" SOCIAL_WEBHOOK_TOKEN)
VERIFY=$(envval "$APP_DIR/.env" WHATSAPP_VERIFY_TOKEN)

say "5/7 WAE Bot settings ($BOT_ENV)"
sudo cp -p "$BOT_ENV" "$BOT_ENV.bak-$(date +%Y%m%d-%H%M%S)"
set_bot_env() { # add KEY=VALUE only when the key is not there yet
  if sudo grep -q "^$1=" "$BOT_ENV"; then echo "  $1 already set: left as it is"; else printf '%s=%s\n' "$1" "$2" | sudo tee -a "$BOT_ENV" >/dev/null; echo "  $1 added"; fi
}
set_bot_env LEAD_BOT_URL http://127.0.0.1:8000
set_bot_env LEAD_BOT_TOKEN "$API_TOKEN"
set_bot_env SOCIAL_INBOX_TOKEN "$SOCIAL_TOKEN"
if ! sudo grep -q "^SOCIAL_INBOX_ACCOUNTS=" "$BOT_ENV"; then
  ask LI "OpenPost account id of the LinkedIn page (Enter to skip)"
  ask XA "OpenPost account id of the X account (Enter to skip)"
  ACC=""
  [ -n "$LI" ] && ACC="linkedin:$LI"
  [ -n "$XA" ] && ACC="${ACC:+$ACC,}x:$XA"
  [ -n "$ACC" ] && set_bot_env SOCIAL_INBOX_ACCOUNTS "$ACC" || echo "  SOCIAL_INBOX_ACCOUNTS skipped: social posts will be refused until it is set"
fi

say "6/7 Service"
sudo cp "$APP_DIR/deploy/wae-post-agent.service" /etc/systemd/system/wae-post-agent.service
sudo systemctl daemon-reload
sudo systemctl enable wae-post-agent >/dev/null 2>&1
sudo systemctl restart wae-post-agent
sleep 4
sudo systemctl is-active --quiet wae-post-agent || { sudo journalctl -u wae-post-agent -n 30 --no-pager; die "The service did not start (log above)."; }
curl -fsS -o /dev/null -w "docs page: HTTP %{http_code}\n" http://127.0.0.1:8000/docs
echo "status: $(curl -fsS -H "Authorization: Bearer $API_TOKEN" http://127.0.0.1:8000/api/status || echo unreachable)"

say "7/7 Two manual steps left"
cat <<EOF

A) nginx: inside the existing server { } block of ai.wae.company, above "location /", add

    location = /whatsapp/webhook {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        client_max_body_size 1m;
    }

   then:  sudo nginx -t && sudo systemctl reload nginx

B) Meta: register the webhook for the business number (field "messages"):
     Callback URL : https://ai.wae.company/whatsapp/webhook
     Verify token : $VERIFY
   The WAE Bot's number already has a webhook of another product: set it as an override for this one number, do not replace the app's callback URL.

Then copy the new wae-bot-server folder (social-inbox.js, server.js) and:  sudo systemctl restart wae-bot
Logs:  sudo journalctl -u wae-post-agent -f
EOF
