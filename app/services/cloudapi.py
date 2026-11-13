"""Meta WhatsApp Cloud API transport (the official alternative to the unofficial OpenWA gateway).

Chats keep the same shape the rest of the agent already uses: "<digits>@c.us" (digits = country code + number, no "+").
Incoming webhook bodies are turned into OpenWA-shaped message events (see events()), so storage, drafting, approval and
the chat policy stay exactly as they are.

Settings (.env, used when WHATSAPP_PROVIDER=cloud):
  WHATSAPP_PHONE_NUMBER_ID   Meta's id of the business number (not the phone number itself)
  WHATSAPP_ACCESS_TOKEN      permanent token of a system user (WhatsApp Business messaging permission)
  WHATSAPP_APP_SECRET        the Meta app's secret: signs every webhook call (X-Hub-Signature-256)
  WHATSAPP_VERIFY_TOKEN      any long random text; Meta sends it back once when the webhook URL is registered
  CLOUD_OWNER_TEMPLATE       optional: approved template with ONE body variable {{1}}; used for owner notifications when WhatsApp
                             refuses plain text (plain text only works within 24 hours after the owner last wrote to the number)
  CLOUD_OWNER_TEMPLATE_LANG  language code of that template (default en)
"""
import hashlib
import hmac
import os
import re

import requests

GRAPH = "https://graph.facebook.com/v21.0"
TEXT_MAX = 4096  # WhatsApp's limit of a text message
REENGAGEMENT = 131047  # "more than 24 hours since the customer last replied": only a template may be sent


def _digits(chat):
    """"919876543210@c.us" -> "919876543210". The Cloud API has no group chats."""
    if not isinstance(chat, str) or not chat.endswith("@c.us") or not chat[:-5].isdigit():
        raise ValueError("The WhatsApp Cloud API only supports individual chats (digits@c.us)")
    return chat[:-5]


def _headers():
    return {"Authorization": "Bearer " + os.environ["WHATSAPP_ACCESS_TOKEN"]}


def _post_message(payload):
    phone_id = os.environ["WHATSAPP_PHONE_NUMBER_ID"]
    return requests.post(f"{GRAPH}/{phone_id}/messages", headers=_headers(), json=payload, timeout=30, allow_redirects=False)


def _error_code(response):
    try:
        return int(response.json()["error"]["code"])
    except (ValueError, KeyError, TypeError):
        return None


def _for_template(text):
    """A template variable may not hold new lines, tabs or long runs of spaces."""
    return re.sub(r" {4,}", "   ", re.sub(r"\s*\n+\s*", " | ", text.replace("\t", " ")))[:900]


def send_text(chat, text):
    """Sends a text message and returns its message id. Raises on any refusal; a timeout stays ambiguous for the caller."""
    to = _digits(chat)
    if not isinstance(text, str) or not text.strip():
        raise ValueError("Message text cannot be empty")
    if len(text) > TEXT_MAX:
        raise ValueError(f"A WhatsApp message can have at most {TEXT_MAX} characters")
    response = _post_message({"messaging_product": "whatsapp", "recipient_type": "individual", "to": to,
                              "type": "text", "text": {"preview_url": False, "body": text}})
    if 200 <= response.status_code < 300:
        return response.json()["messages"][0]["id"]

    code = _error_code(response)
    template = os.getenv("CLOUD_OWNER_TEMPLATE", "").strip()
    # outside the 24-hour window only the owner's own notifications may fall back to a template (never a customer reply)
    if code == REENGAGEMENT and template and chat == os.getenv("OPENWA_OWNER_CHAT_ID", "").strip():
        retry = _post_message({"messaging_product": "whatsapp", "to": to, "type": "template", "template": {
            "name": template, "language": {"code": os.getenv("CLOUD_OWNER_TEMPLATE_LANG", "en").strip() or "en"},
            "components": [{"type": "body", "parameters": [{"type": "text", "text": _for_template(text)}]}]}})
        if 200 <= retry.status_code < 300:
            return retry.json()["messages"][0]["id"]
        response, code = retry, _error_code(retry)
    raise RuntimeError(f"WhatsApp Cloud API returned HTTP {response.status_code}" + (f" (error code {code})" if code else ""))


def verify_signature(raw, header):
    """True when `header` (X-Hub-Signature-256) is the HMAC of the exact raw body made with the app secret."""
    secret = os.getenv("WHATSAPP_APP_SECRET", "")
    if not secret or not isinstance(header, str):
        return False
    expected = "sha256=" + hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected.encode(), header.encode())


def events(payload):
    """Cloud API webhook body -> list of OpenWA-shaped "message.received" events (text messages only).

    sessionId is the id of the business number that received the message: the caller drops events for other numbers
    (one Meta app can carry several numbers). Delivery receipts and other field types are ignored."""
    if not isinstance(payload, dict) or payload.get("object") != "whatsapp_business_account":
        raise ValueError("Not a WhatsApp webhook")
    found = []
    for entry in payload.get("entry") or []:
        for change in (entry.get("changes") or []) if isinstance(entry, dict) else []:
            if not isinstance(change, dict) or change.get("field") != "messages":
                continue
            value = change.get("value") or {}
            phone_id = (value.get("metadata") or {}).get("phone_number_id")
            for message in value.get("messages") or []:
                if not isinstance(message, dict) or message.get("type") != "text":
                    continue
                sender, body = message.get("from"), (message.get("text") or {}).get("body")
                if not isinstance(sender, str) or not sender.isdigit() or not isinstance(body, str):
                    continue
                found.append({"sessionId": phone_id, "event": "message.received", "data": {
                    "id": message.get("id"), "chatId": sender + "@c.us", "fromMe": False, "isGroup": False, "body": body}})
    return found


def status():
    """Health of the number for /api/status (keys match the OpenWA version of that answer)."""
    try:
        phone_id = os.environ["WHATSAPP_PHONE_NUMBER_ID"]
        response = requests.get(f"{GRAPH}/{phone_id}", headers=_headers(), timeout=8, allow_redirects=False,
                                params={"fields": "display_phone_number,verified_name,quality_rating,code_verification_status"})
        response.raise_for_status()
        data = response.json()
        return {"gateway_reachable": True, "session_found": True,
                "session_status": data.get("code_verification_status") or "connected",
                "number": data.get("display_phone_number"), "quality_rating": data.get("quality_rating")}
    except (requests.RequestException, ValueError, KeyError):
        return {"gateway_reachable": False, "session_found": None, "session_status": None}
