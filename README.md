# Company operations agent

One LangGraph agent with tools for WhatsApp leads, social post drafts, and follow-up reminders. FastAPI exposes the agent and review actions to a separate UI. Both workflows use the same configured Groq model.

## Structure

```text
app/
  agent/       # Shared tool-calling agent and constrained lead drafting
  tools/       # WhatsApp operations, social workflow, model tool registry
  services/    # Model provider, OpenWA transport, background scheduler
  storage/     # SQLite schema and compatibility migrations
  api/         # FastAPI app and API operations
  cli.py       # Local commands
```

Use `python -m app` for all commands, or `app.api.main:app` as the ASGI entry point. All implementation code lives under `app/`.

## Setup

Python 3.11+ and an OpenWA gateway are required for live WhatsApp use.

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
# Only for a new setup; keep an existing .env:
Copy-Item .env.example .env
```

Set `GROQ_API_KEY` and update `company.json` with real business facts. Configure the OpenWA gateway URL, key, session ID, webhook secret, owner notification chat, and allowed test chat in `.env`. `OPENWA_BASE_URL` excludes `/api`. Set `WHATSAPP_API_TOKEN` for your UI and exact browser origins in `WHATSAPP_API_ORIGINS`.

Existing `.env`, SQLite data, social drafts in `posts/`, and OpenWA sessions are retained. The agent defaults to `AGENT_TIMEZONE=Asia/Kolkata` when interpreting reminder times.

## Start the backend

```powershell
.\.venv\Scripts\python -m app serve --host 0.0.0.0
```

Alternative: `python -m uvicorn app.api.main:app --host 0.0.0.0 --port 8000`.

Run one server process with one worker and no reload. The application lifespan starts inbox processing and reminder delivery, then stops the worker on shutdown. Do not start another copy if one is already running.

Open `http://localhost:8000/docs` for Swagger or `/redoc` for ReDoc. Authorize with the `WHATSAPP_API_TOKEN` value. [API.md](API.md) describes the request and response contracts.

## Ask the shared agent

Use `POST /api/agent/run` with a body such as:

```json
{"message":"Show my leads and pending reminders"}
```

Or use the CLI:

```powershell
python -m app run "Draft a LinkedIn post introducing our company"
```

The agent selects tools to read lead facts and conversations, create WhatsApp reply drafts, draft social posts, and create/list/cancel reminders. `GET /api/agent/tools` lists the registered tools and schemas. The response includes tool calls and their results, not just the final text.

Each request has a fresh reasoning context. Persistent leads, conversations, drafts, and reminders are retrieved through tools. Relative reminder times use the configured timezone. The agent asks when the target lead or time is unclear.

Customer WhatsApp messages use a constrained extraction-and-drafting path. They are not operator requests and cannot invoke the full tool set. Conversation content and tool outputs are treated as data.

**Sending a saved WhatsApp draft requires explicit approval.** Send `{"message":"send draft #3"}` to `/api/agent/run`, or run `python -m app run "send draft #3"`. This sends the saved text of that draft. `send it` asks for the draft ID. The command is checked deterministically outside the model loop; customer messages and model tool output cannot authorize a send. The direct approval endpoint/CLI also remains available. Social publishing still requires its separate explicit approval action.

## Native publishing (LinkedIn, X, Facebook, Instagram)

`app/services/social_adapters.py` holds direct API adapters, so the webhook is optional. Set the variables listed in `.env.example`, then:

```powershell
python -m app publish-direct posts/YOUR-POST-ID.json          # dry run: prints the requests only
python -m app publish-direct posts/YOUR-POST-ID.json --live   # really posts
```

Instagram drafts need a public HTTPS `image_url` field added to the JSON. A successful live post sets `status` to `published` and stores `remote_id`. There are no retries; after a timeout, check the platform before re-running. Tests mock all HTTP calls.
`--live` posts at once with the tokens in `.env` and can only be started by a person at the command line: the agent's tools cannot publish. At WAE the reviewed route is the WAE Bot's OpenPost door (`SOCIAL_WEBHOOK_URL`, see above), which makes a draft that a person schedules in OpenPost.

## Official WhatsApp (Cloud API)

OpenWA is an unofficial gateway and carries a ban risk. For a company number use Meta's official **WhatsApp Cloud API** instead:
set `WHATSAPP_PROVIDER=cloud` and fill the `WHATSAPP_*` values of `.env.example`. Nothing else in the agent changes: chats stay `digits@c.us`
(country code + number, no `+`, for example `919876543210@c.us`), and `OPENWA_TEST_CHAT_ID`, `OPENWA_OWNER_CHAT_ID` and `OPENWA_ALLOW_ALL_CHATS` keep their names and meaning.
The `OPENWA_BASE_URL`, `OPENWA_API_KEY`, `OPENWA_SESSION_ID` and `OPENWA_WEBHOOK_SECRET` values are not needed in this mode.

Setup (Meta side): in the Meta app that owns the business number, add the WhatsApp product, create a system user with a permanent token
(`whatsapp_business_messaging` permission), and note the phone number id and the app secret. Register the webhook:

- Callback URL: `https://<your-host>/whatsapp/webhook` (Meta needs public HTTPS; put nginx or a tunnel in front of port 8000)
- Verify token: the same `WHATSAPP_VERIFY_TOKEN`
- Field: `messages`

If another product already uses the app's webhook, set a webhook override for this one phone number in Meta instead of changing the app's callback URL.
Messages to other numbers of the same app are acknowledged and ignored, so the two never mix.

Rules of the Cloud API that matter here: a free-text reply only works within 24 hours after the customer last wrote (the bot answers customers, so this normally holds);
the owner notification outside that window needs an approved template (`CLOUD_OWNER_TEMPLATE`, one body variable); groups are not supported (only `@c.us` chats);
each conversation is billed by Meta. A refused or timed-out send is marked `uncertain` and never resent automatically, as before.
`GET /api/status` shows the number, its quality rating and verification state instead of the OpenWA session.

## Connect OpenWA locally

With OpenWA in Docker Desktop and the Python bot on Windows, register:

- URL: `http://host.docker.internal:8000/openwa/webhook`
- Event: `message.received`
- Secret: the same `OPENWA_WEBHOOK_SECRET` as the bot (at least 16 characters)

The `openwa.local.yml` overlay allows that exact host through OpenWA's URL guard. Apply it alongside the gateway's original compose file, adjusting paths as needed:

```powershell
docker compose --project-directory D:\Watsapp-Gateway\OpenWA -f D:\Watsapp-Gateway\OpenWA\docker-compose.dev.yml -f D:\WAE-bot\openwa.local.yml up -d --no-build openwa
```

Keep both compose files in future recreate commands. No public tunnel is needed locally. Port 8000 listens on all interfaces for Docker connectivity; restrict it to the local/Docker network with your firewall. The receiver verifies raw-body HMAC and deduplicates message IDs before processing.

## Automatic replies (optional)

By default every reply is a draft that a person approves. With `AUTO_REPLY=on` in `.env` (restart after changing it) a reply to a **lead** is sent to the customer right away,
through the same send path as an approval, and the owner gets a notice saying it was sent. Limits: individual chats only (a group reply still waits for a person),
`AUTO_REPLY_MAX_PER_CHAT_HOUR` (6) replies per customer per hour and `AUTO_REPLY_MAX_PER_DAY` (1000) in total; over a limit the reply stays a draft.
Messages that are not business enquiries get no reply. A failed or timed-out automatic send is marked `uncertain`, is never resent, and the owner is told.
Nobody reads an automatic reply first, so keep `company.json` accurate (its `never_state` line keeps fees, dates and guarantees out of replies) and check `python -m app drafts` regularly.

## WhatsApp review and reminders

For temporary unrestricted testing, set `OPENWA_ALLOW_ALL_CHATS=true` and restart.
This overrides the saved test chat across incoming messages, tools, the API, and
approval commands, individual chats only: group chats stay ignored unless `OPENWA_ALLOW_GROUPS=true` is also set (a group set as `OPENWA_TEST_CHAT_ID` still works). Set it back to `false` and restart to
restore `OPENWA_TEST_CHAT_ID`. `/api/status` reports `allow_all_chats`. Explicit send
approval is still required in either mode; outgoing messages are still ignored.

`OPENWA_TEST_CHAT_ID` restricts incoming messages, tool access, approvals, and reminders to one exact chat. Blank/missing blocks all customer chats. Individual `@c.us`, `@lid`, and group `@g.us` IDs are supported. Groups are treated as one shared conversation; an approved group reply goes to the whole group. Your outgoing messages and messages without text are ignored. Restart after changing the test chat.

```powershell
python -m app leads
python -m app drafts
python -m app approve 1
# Or approve edited text instead:
python -m app approve 1 --text "Thank you. Where is your office located?"
python -m app reject 2
```

Approval sends a real reply. New incoming messages supersede unsent drafts and cancel pending reminders for that chat. Sent bot replies are available as context; replies sent manually from your phone are not synced yet.

```powershell
$due = (Get-Date).AddMinutes(2).ToString("yyyy-MM-ddTHH:mm:sszzz")
python -m app remind --chat "YOUR-ALLOWED-CHAT-ID" --at "$due" --note "Follow up about the quotation"
python -m app reminders
python -m app cancel-reminder 1
```

Reminders notify `OPENWA_OWNER_CHAT_ID`, not the customer. Self-chat notifications work in the current local setup. Reminders persist across restarts; overdue ones run when the service resumes. Keep the server running to deliver them. The agent can create reminders when instructed; it does not automatically invent follow-up schedules for inbound customer messages.

## Social posts

```powershell
python -m app draft --platform linkedin --topic "Introduce our customer support service"
# Review the saved JSON first, then explicitly submit it:
python -m app publish posts/YOUR-POST-ID.json
```

**WAE setup:** point `SOCIAL_WEBHOOK_URL` at the WAE Bot server (`https://ai.wae.company/inbox/social`) and set `SOCIAL_WEBHOOK_TOKEN` to its `SOCIAL_INBOX_TOKEN`. The post then becomes a **draft** in OpenPost (posting.weareengineer.com) for LinkedIn or X; a person schedules or publishes it there, so `submitted` means "draft created in OpenPost". Instagram needs media and is refused (HTTP 422).

Social posts remain JSON files in `posts/`. Publishing requires an HTTPS `SOCIAL_WEBHOOK_URL`, with optional `SOCIAL_WEBHOOK_TOKEN` bearer authentication. The receiver must route the platform, authenticate accounts, and deduplicate by the `Idempotency-Key` post ID. A 2xx response marks the post `submitted`; it does not confirm platform publication. After a timeout, check the receiver before retrying. Instagram requires media attached by the receiving integration.

## Tests

```powershell
python -m pip install -r requirements-dev.txt
python -m unittest discover -s tests -v
```

Tests mock model and publishing calls; they do not consume model credits or send real WhatsApp messages. FastAPI tests cover authentication, single-chat restrictions, approval, reminders, signatures, and worker lifecycle. Agent tests verify tool selection and the absence of send/publish tools.

## Operations

The SQLite database contains customer messages; protect and back it up. It, `.env`, generated posts, logs, and the local virtual environment are git-ignored. Customer content and company facts are sent to your configured Groq model for drafting/extraction.

Model failures stay queued with a 60-second retry delay. Reminder polling runs about every five seconds; external calls can delay it. Ambiguous WhatsApp send/notification failures become `uncertain` and are not automatically resent. Inspect the chat/gateway before manual action. `sent` means gateway acceptance, not confirmed reading or delivery.

OpenWA is an independent, unofficial WhatsApp gateway. Consult its [documentation](https://docs.open-wa.org/) for installation, account behavior, and gateway configuration.
