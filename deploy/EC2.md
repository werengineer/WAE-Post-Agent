# WAE Post Agent on the WAE Bot EC2 server (ai.wae.company)

The agent runs next to the WAE Bot as a second service: Python 3.11+, systemd, listening on `127.0.0.1:8000` only.
The internet reaches just one path, `https://ai.wae.company/whatsapp/webhook` (Meta's webhook), through nginx.
The WAE Bot server talks to the agent on `http://127.0.0.1:8000` (admin panel: drafts, approve, reminders).

## 1. Python and the code

```bash
python3 --version        # 3.11 or newer is needed
```

Ubuntu 24.04 has 3.12: `sudo apt-get install -y python3-venv`.
Ubuntu 22.04 has 3.10: `sudo add-apt-repository -y ppa:deadsnakes/python && sudo apt-get install -y python3.11 python3.11-venv` and use `python3.11` below.

```bash
sudo mkdir -p /opt/wae-post-agent && sudo chown wae:wae /opt/wae-post-agent
sudo -u wae git clone https://github.com/werengineer/WAE-Post-Agent.git /opt/wae-post-agent
cd /opt/wae-post-agent
sudo -u wae python3 -m venv .venv
sudo -u wae .venv/bin/python -m pip install -r requirements.txt
sudo -u wae cp .env.example .env && sudo chmod 600 .env
```

(If the repo is private on your side, clone with a token or copy the folder with `scp`, excluding `.env`, `.venv`, `*.sqlite3`, `posts/`.)

Run the tests once before going on (they mock the model, Meta and OpenPost: no credits used, no real message sent):

```bash
cd /opt/wae-post-agent && sudo -u wae .venv/bin/python -m pip install -r requirements-dev.txt && sudo -u wae .venv/bin/python -m unittest discover -s tests -v
```

All tests must pass (`tests/test_cloud_api.py` covers the Cloud API part). If one fails, stop and send the output.

## 2. `.env` (edit `/opt/wae-post-agent/.env`)

```env
GROQ_API_KEY=...                       # console.groq.com
WHATSAPP_PROVIDER=cloud
WHATSAPP_PHONE_NUMBER_ID=...           # Meta: WhatsApp > API setup, the id of the number (not the phone number)
WHATSAPP_ACCESS_TOKEN=...              # system user permanent token (whatsapp_business_messaging)
WHATSAPP_APP_SECRET=...                # Meta app > Settings > Basic > App secret
WHATSAPP_VERIFY_TOKEN=...              # make one: openssl rand -hex 24
OPENWA_TEST_CHAT_ID=91XXXXXXXXXX@c.us  # the ONE customer chat the agent may read and answer (digits only, country code first)
OPENWA_OWNER_CHAT_ID=91XXXXXXXXXX@c.us # who gets "new lead / draft ready" notifications
WHATSAPP_API_TOKEN=...                 # make one: openssl rand -hex 24 (the WAE Bot server uses it as LEAD_BOT_TOKEN)
WHATSAPP_API_ORIGINS=                  # empty: no browser talks to the agent directly
SOCIAL_WEBHOOK_URL=https://ai.wae.company/inbox/social
SOCIAL_WEBHOOK_TOKEN=...               # the same value as SOCIAL_INBOX_TOKEN of the WAE Bot server
AGENT_TIMEZONE=Asia/Kolkata
```

Also edit `company.json` with the real WAE facts (name, description, audience, tone, website): the drafts only use what is written there.
Leave `OPENWA_ALLOW_ALL_CHATS=false`: that keeps the agent on the one test chat. Open it up only when you decide to answer every customer.

## 3. Service

```bash
sudo cp /opt/wae-post-agent/deploy/wae-post-agent.service /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now wae-post-agent
sudo systemctl status wae-post-agent --no-pager
curl -s http://127.0.0.1:8000/docs -o /dev/null -w "%{http_code}\n"     # 200
curl -s -H "Authorization: Bearer $WHATSAPP_API_TOKEN" http://127.0.0.1:8000/api/status   # number, quality rating, verification
```

Run exactly one copy (one worker, no reload): each process starts its own background worker.

## 4. nginx: only the webhook path goes out

Inside the existing `server { ... }` block of `ai.wae.company`, above `location /`:

```nginx
location = /whatsapp/webhook {
    proxy_pass http://127.0.0.1:8000;
    proxy_set_header Host $host;
    client_max_body_size 1m;
}
```

`sudo nginx -t && sudo systemctl reload nginx`. The rest of the agent API stays private (localhost only).

## 5. Meta: register the webhook

- Callback URL `https://ai.wae.company/whatsapp/webhook`, verify token = `WHATSAPP_VERIFY_TOKEN`, field `messages`.
- The business number the WAE Bot already sends from has a webhook that belongs to another product. Do **not** replace the app-level callback URL. Set an override for this one number instead
  (Meta: "Override the callback URL", per phone number: `POST /<PHONE_NUMBER_ID>` with `webhook_configuration: {override_callback_uri, verify_token}`); check the current Meta docs for the exact call.
- A brand-new number registered to Cloud API for the agent is the cleaner choice if you do not want to touch the existing one.
- Meta's "Test" button must answer 200: `sudo journalctl -u wae-post-agent -f` shows the call.

## 6. WAE Bot server (admin panel link and social door)

In `/etc/wae-bot.env`:

```env
LEAD_BOT_URL=http://127.0.0.1:8000
LEAD_BOT_TOKEN=<the agent's WHATSAPP_API_TOKEN>
SOCIAL_INBOX_TOKEN=<same as the agent's SOCIAL_WEBHOOK_TOKEN>
SOCIAL_INBOX_ACCOUNTS=linkedin:<OpenPost account id>,x:<OpenPost account id>
OPENPOST_TOKEN=...            # already set if posting is on
OPENPOST_WORKSPACE_ID=...
```

Copy the updated `wae-bot-server` folder (it has the new `social-inbox.js`) and `sudo systemctl restart wae-bot`.
Account ids: `GET /api/posting` of the WAE Bot lists the OpenPost accounts per workspace. LinkedIn and X must already be connected in OpenPost.

## 7. Test, in this order

1. Send a message from the allowed chat to the business number. A lead and a reply draft appear (`/api/drafts`, or the admin panel) and the owner chat gets a notification.
2. Approve the draft: the reply reaches the customer chat. Nothing is sent before approval.
3. `python -m app draft --platform linkedin --topic "..."`, check `posts/<id>.json`, then `python -m app publish posts/<id>.json`: a DRAFT appears in OpenPost (posting.weareengineer.com); schedule it there.
4. Messages from any other chat are ignored (that is the test-chat boundary working).

## Cloud API reminders

- A free-text reply works within 24 hours after the customer's last message. For owner notifications outside that window, create an approved template with one body variable and set `CLOUD_OWNER_TEMPLATE`.
- Meta bills per conversation. Groups are not supported.
- Backups: `/opt/wae-post-agent/whatsapp.sqlite3` holds customer messages: protect and back it up.

## OpenWA mode (QR code, no Meta secret)

Choose this when the business number is linked by scanning a QR code instead of through Meta. It is unofficial (the number can be restricted or banned): use a number you can afford to lose.

1. `bash deploy/openwa-setup.sh`: installs Docker if missing, runs OpenWA on `127.0.0.1:2785` only, makes the session `wae-leads`, registers the webhook to the agent and saves the connection values in `/opt/openwa/.wae-openwa.env`. It shows the free memory and disk first: OpenWA needs about 1 GB of memory and a few GB of disk, so on a small server that also runs the WAE Bot a separate server is safer.
2. Scan the QR code through an SSH tunnel (the script prints the exact command): open `http://localhost:2785` on your laptop, start the session, then WhatsApp > Linked devices > Link a device.
3. `bash deploy/install.sh` and answer `1` (OpenWA). It reads the saved values, so there is no secret to type. No nginx step and no Meta step.
4. Keep ports 2785 and 8000 closed in the security group (only 22, 80 and 443 are open today). In this mode the agent listens on all interfaces so that the OpenWA container can reach it, which is safe only while port 8000 is closed.
