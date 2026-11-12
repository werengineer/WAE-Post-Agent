# Basic company social media agent

A small Python agent using LangGraph for workflow and LangChain's chat-model integration to draft company posts. It generates text for LinkedIn, X, or Instagram, checks length, and saves a JSON draft. A separate command submits the reviewed text to a publishing webhook.

## Setup (PowerShell, Python 3.11+)

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Put your model API key in `.env` and replace the example company information in `company.json`.

## Draft and publish

```powershell
.\.venv\Scripts\python agent.py draft --platform linkedin --topic "Introduce our new customer support service"
```

Review or edit the generated file in `posts/`, then submit that exact draft:

```powershell
.\.venv\Scripts\python agent.py publish posts/YOUR-POST-ID.json
```

Drafting does not publish anything. Publishing requires `SOCIAL_WEBHOOK_URL`; optionally set `SOCIAL_WEBHOOK_TOKEN` for Bearer authentication.

## Connect your social accounts

Configure an HTTPS webhook in n8n, Make, or your own service to accept a JSON body with `post_id`, `company`, `platform`, `text`, `created_at`, and `status`. The receiving workflow must authenticate the request, route by platform, and call the relevant social API using your company's account credentials. This starter does not include native platform adapters or account authentication.

The endpoint should deduplicate by the `Idempotency-Key` header (the post ID). A 2xx response marks a draft as `submitted`, meaning the endpoint accepted it; it does not confirm the social platform published it. There are no automatic retries: after a timeout, check the receiving service before retrying. Endpoint deduplication is necessary if the network fails after acceptance. Run only one publisher process per draft.

Instagram requires media, so its receiving workflow must attach an image or video. Character checks here use Python string length; final platform rules, including X's URL and Unicode weighting, belong in the publishing integration.

## Native publishing (LinkedIn, X, Facebook, Instagram)

`social/` holds direct API adapters, so the webhook is optional. Set the variables listed in `.env.example`, then:

```powershell
.\.venv\Scripts\python agent.py publish-direct posts/YOUR-POST-ID.json          # dry run: prints the request only
.\.venv\Scripts\python agent.py publish-direct posts/YOUR-POST-ID.json --live   # really posts
```

Instagram drafts need a public HTTPS `image_url` field added to the JSON. A successful live post sets `status` to `published` and stores `remote_id`. There are no retries; after a timeout, check the platform before re-running. Tests mock all HTTP calls.

## Workflow

`START → draft with model → validate length → save JSON → END`

Use Windows Task Scheduler or cron to invoke the draft command on a schedule. Publish reviewed files using the publish command; unattended approval, content calendars, media generation, and scheduling are intentionally outside this basic starter.

## Tests

```powershell
.\.venv\Scripts\python -m unittest discover -s tests -v
```

Tests mock the model and HTTP endpoint; they do not consume API credits or publish posts.
