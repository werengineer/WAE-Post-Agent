"""WhatsApp Cloud API (Meta) gateway: webhook parsing/verification and guarded sending.

Nothing is sent unless WHATSAPP_SEND_ENABLED=1 AND a message was approved in the outbox.
Credentials are read from the environment only (WHATSAPP_TOKEN, WHATSAPP_PHONE_NUMBER_ID,
WHATSAPP_VERIFY_TOKEN, WHATSAPP_APP_SECRET).
"""

import hashlib
import hmac
import os

import requests

GRAPH = "https://graph.facebook.com/v21.0"


def verify_signature(raw_body: bytes, header: str, app_secret: str) -> bool:
    if not app_secret or not header or not header.startswith("sha256="):
        return False
    expected = hmac.new(app_secret.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, header[7:])


def verify_challenge(params: dict, verify_token: str) -> str | None:
    """GET handshake Meta performs when the webhook URL is registered."""
    if (verify_token and params.get("hub.mode") == "subscribe"
            and hmac.compare_digest(params.get("hub.verify_token", ""), verify_token)):
        return params.get("hub.challenge", "")
    return None


def parse_inbound(payload: dict) -> list[dict]:
    """Extract text messages: [{wa_id, phone, name, text}]. Non-text types become a marker."""
    out = []
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            names = {c.get("wa_id"): c.get("profile", {}).get("name", "")
                     for c in value.get("contacts", [])}
            for m in value.get("messages", []):
                text = m.get("text", {}).get("body") if m.get("type") == "text" else \
                    f"[{m.get('type', 'unknown')} message]"
                out.append({"wa_id": m.get("id"), "phone": m.get("from", ""),
                            "name": names.get(m.get("from"), ""), "text": text or ""})
    return out


def send_text(to: str, body: str) -> str:
    """Send a free-form text (only valid inside the 24h customer-service window)."""
    if os.getenv("WHATSAPP_SEND_ENABLED") != "1":
        raise RuntimeError("Sending disabled: set WHATSAPP_SEND_ENABLED=1 after review")
    token, phone_id = os.getenv("WHATSAPP_TOKEN"), os.getenv("WHATSAPP_PHONE_NUMBER_ID")
    if not token or not phone_id:
        raise RuntimeError("WHATSAPP_TOKEN and WHATSAPP_PHONE_NUMBER_ID are required")
    r = requests.post(f"{GRAPH}/{phone_id}/messages",
                      headers={"Authorization": f"Bearer {token}"},
                      json={"messaging_product": "whatsapp", "to": to, "type": "text",
                            "text": {"body": body}}, timeout=30, allow_redirects=False)
    if not 200 <= r.status_code < 300:
        raise RuntimeError(f"WhatsApp API returned HTTP {r.status_code}")
    return r.json().get("messages", [{}])[0].get("id", "")
