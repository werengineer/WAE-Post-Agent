# WhatsApp lead automation (WhatsApp Cloud API)

Flow: lead replies on WhatsApp -> webhook (`serve`) -> status classified + follow-up scheduled
-> suggested reply queued in the **outbox as `pending_approval`** -> a person approves -> `send`.
`remind` queues a follow-up reminder for Lokesh; `digest` queues a manager-style lead update for the report chat.
Opt-outs ("stop") cancel follow-ups and queued messages and block sending.

Safety: nothing is sent unless `WHATSAPP_SEND_ENABLED=1` and the message was approved.

## Environment (set in `.env`, never commit)
WHATSAPP_TOKEN, WHATSAPP_PHONE_NUMBER_ID, WHATSAPP_VERIFY_TOKEN, WHATSAPP_APP_SECRET,
LOKESH_WHATSAPP (digits with country code), REPORT_CHAT_WHATSAPP, WHATSAPP_SEND_ENABLED, LEADS_DB.

## Usage
    python -m lead_bot.cli serve --port 8080    # put behind HTTPS, register URL in Meta dashboard
    python -m lead_bot.cli add-lead 919876543210 --name "Asha Rao"
    python -m lead_bot.cli outbox ; python -m lead_bot.cli approve 3 ; python -m lead_bot.cli send
    # cron: hourly `remind`, daily `digest`

Tests: `python -m unittest tests.test_lead_bot -v`

## Limits
Free-text sends only work inside WhatsApp's 24h window after the lead's last message; first-contact
and late follow-ups need Meta-approved templates (not implemented: `send_text` only).
Classification is keyword rules (English/Hinglish) - tune on real replies.
