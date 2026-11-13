# Company agent UI backend

FastAPI serves the shared agent, social tools, signed OpenWA webhook, and UI API, by default at
`http://127.0.0.1:8000`. Install the updated dependencies, then choose one entry point:

```powershell
python -m pip install -r requirements.txt
python -m app serve --host 0.0.0.0
# Alternative (choose one):
python -m uvicorn app.api.main:app --host 0.0.0.0 --port 8000
```

Interactive Swagger documentation is at `/docs`, ReDoc at `/redoc`, and the generated
OpenAPI schema at `/openapi.json`. Click **Authorize** in Swagger and enter only the
`WHATSAPP_API_TOKEN` value. Documentation/schema pages contain no lead data; API
operations still require bearer authentication. Request models and pagination
constraints are described in the schema. Invalid input retains HTTP 400 and the
`error` field for compatibility; FastAPI validation also provides `details`.

The reminder/drafting worker starts in FastAPI's lifespan and stops at shutdown.
Use **one Uvicorn worker**, with no reload, against a database: each process would
otherwise start its own background worker. Restart an existing process after changes.

## Authentication and browser access

Set a private random `WHATSAPP_API_TOKEN` in `.env`. Every API request requires:

```http
Authorization: Bearer YOUR_WHATSAPP_API_TOKEN
```

This token is separate from `OPENWA_API_KEY`; never send the OpenWA key to the UI.
An empty API token disables API access (503) while the signed webhook continues
working. API authentication never bypasses the webhook HMAC check. Requests with
bad/missing credentials return 401. Responses are JSON with `Cache-Control: no-store`.

For a browser UI, set `WHATSAPP_API_ORIGINS` to exact origins, for example
`http://localhost:3000,http://localhost:5173`. Other origins are rejected with 403.
Preflight OPTIONS requests from approved origins work without a bearer token.
Server-to-server requests without an Origin header still require the token.
This is a single-operator local API; it does not implement user accounts or roles.
Supply the token privately at runtime; do not commit it or embed it in a public UI bundle.

## WhatsApp webhooks

- `POST /openwa/webhook` — OpenWA gateway events (`X-OpenWA-Signature` HMAC), used when `WHATSAPP_PROVIDER=openwa` (default).
- `GET /whatsapp/webhook` — Meta's one-time URL check (`hub.mode`, `hub.verify_token`, `hub.challenge`), `WHATSAPP_PROVIDER=cloud` only.
- `POST /whatsapp/webhook` — Meta Cloud API message calls (`X-Hub-Signature-256` HMAC of the raw body with `WHATSAPP_APP_SECRET`); answers 404 when the provider is `openwa`.
  Text messages to the configured `WHATSAPP_PHONE_NUMBER_ID` are stored; everything else is acknowledged with `200 OK` and dropped.

## Routes

### Combined agent and social tools

- `GET /api/agent/tools` — registered model-callable tools and their input schemas.
- `POST /api/agent/run` — operator request, for example
  `{"message":"List my leads and pending follow-up reminders"}`. The agent selects
  tools and returns `reply`, `tool_calls`, and `tool_results` (including tool failures).
  Calls may create drafts or reminders. An exact operator message such as
  `{"message":"send draft #3"}` approves and sends that saved WhatsApp draft.
  `please send draft 3` and `approve and send draft #3` are also supported.
  `send it` asks for a draft ID. These commands bypass the model and reuse the
  existing approval guard; they never permit arbitrary text or recipients.
  Only a pending draft in the allowed test chat can be sent. The response has
  `tool_results[].content.ok` indicating whether sending succeeded; inspect it,
  because rejected commands and uncertain sends still return HTTP 200 with `ok:false`.
  Social posts cannot be published through the agent.
  Each request starts a fresh reasoning context, with access to persisted business
  records through tools. Requests have a bounded tool loop; a 409 step-limit error
  may follow partially completed tools, so inspect records before retrying.
- `GET /api/posts` — up to 50 most recent saved social posts, as `{"items":[...]}`.
- `POST /api/posts/draft` — `{"platform":"linkedin","topic":"New service"}`;
  creates an unsent draft, returning 201 with text, post ID, and saved-file path.
  Supported platforms are `linkedin`, `x`, and `instagram`.
- `POST /api/posts/{post_id}/publish` — explicit operator approval to submit a
  reviewed social draft to `SOCIAL_WEBHOOK_URL`. This action sends an external
  request; it is not available as an agent tool. Publishing retains the existing
  webhook idempotency-key behavior. After a timeout, inspect the receiver before
  retrying. `submitted` means webhook acceptance, not confirmed platform posting.

The agent's inbound WhatsApp path is constrained to lead extraction and reply
drafting. A customer message never receives authority to call the operator tools.
All agent and social routes require the same API bearer authentication.

### WhatsApp leads, replies, and reminders

`OPENWA_ALLOW_ALL_CHATS=true` temporarily overrides the single-chat restriction
across ingestion, tools, listings, history, and draft approval. `/api/status`
reports `allow_all_chats`. Set it to `false` and restart to restore the saved test
chat. Explicit send commands/approval are still required.

All WhatsApp lead data and mutations are restricted to `OPENWA_TEST_CHAT_ID`. Rows from
earlier test chats remain stored but are hidden from this API. Missing/blank
configuration returns empty lists and blocks mutations outside the configured chat.

- `GET /api/status` — read-only gateway/session connection check. Returns
  `gateway_reachable`, `session_found`, `session_status`, and `test_chat_id`.
  No credentials or session authentication data are returned.
- `GET /api/leads` — list leads. Each lead has `chat`, `details` (a JSON object),
  and `updated_at` (Unix seconds).
- `GET /api/leads/{url-encoded-chat-id}/messages` — captured conversation, newest
  first. Each item has `id`, `text`, `direction` (`inbound` or `outbound`), `state`,
  and `timestamp` (Unix seconds). Only successfully submitted bot replies are
  included as outbound messages. `manual_phone_replies_included` is currently false.
  Old rows created before timestamp support have null timestamps, so their original
  order relative to other old messages cannot be reconstructed. Group inbound
  `text` is a JSON-encoded string containing `sender` and `text`.
- `GET /api/drafts` — list drafts; optional `?state=draft` for pending review.
- `GET /api/drafts/{id}` — get one draft, including its current state and message ID.
- `PATCH /api/drafts/{id}` — save edited text with `{"text":"Reviewed reply"}`.
  This does not send the reply or create another WhatsApp preview notification.
- `POST /api/drafts/{id}/approve` — explicitly send the draft. Use `{}` to send
  saved text, or `{"text":"Final reviewed text"}` to replace and send it in one
  operation. Returns the updated draft. This is the only API action that sends
  a customer reply.
- `POST /api/drafts/{id}/reject` — reject a pending draft; body `{}`.
- `GET /api/reminders` — list reminders; optional `?state=pending`.
- `POST /api/reminders` — create a reminder using the shape below. Returns 201.
- `POST /api/reminders/{id}/cancel` — cancel a pending reminder; body `{}`.

All lists (including messages) support `limit` (default 100, maximum 500) and
`offset` (default 0). They return `{"items": [...], "total": 1, "limit": 100,
"offset": 0}`. Leads sort by most recently updated; drafts/reminders by newest ID.

Create-reminder body:

```json
{
  "chat": "197976601420005@lid",
  "at": "2026-11-07T11:00:00+05:30",
  "note": "Follow up about the quotation"
}
```

Choose an actual future time. `at` must include a timezone offset. Reminder
responses use `due` in ISO UTC, for example `2026-11-07T05:30:00+00:00`.
Reminders notify the owner; they do not message the customer. The serve process
must be running. A new inbound message cancels pending reminders for that chat.

## Errors and sending behavior

Errors have the shape `{"error":"message"}`. Validation errors return 400;
missing or out-of-scope records return 404; invalid state transitions return 409.
Only `draft` state may be edited, approved, or rejected. Only `pending` reminders
may be cancelled. A new customer message supersedes unsent drafts.

If sending fails, approval returns 502 and the draft becomes `uncertain`.
Do not automatically retry approval on an error or timeout. Refresh the draft and
inspect WhatsApp/OpenWA: the send may already have succeeded. Duplicate approval
of an already claimed/sent/uncertain draft is rejected. A successful `sent` state
means gateway acceptance, not confirmed delivery or reading. This API does not
currently offer a reset/resend action for uncertain records.

Existing local CLI commands continue to work. Do not run multiple serve processes
against the same database. The server supports concurrent HTTP requests, each with
its own database connection. SQLite contention/unavailability returns 503.

## Example UI call

```javascript
// Supply the operator's private token at runtime.
async function pendingDrafts(apiToken) {
  const response = await fetch('http://localhost:8000/api/drafts?state=draft', {
    headers: { Authorization: `Bearer ${apiToken}` },
  });
  const result = await response.json();
  if (!response.ok) throw new Error(result.error);
  return result.items;
}
```

For approval, explicitly ask the operator to review the text in your UI, then
POST the action with the bearer header and `Content-Type: application/json`.
