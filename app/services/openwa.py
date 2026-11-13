"""OpenWA HTTP transport."""
import os
from urllib.parse import quote, urlparse
import requests


def send_text(chat, text):
    base = os.environ["OPENWA_BASE_URL"].rstrip("/")
    parsed = urlparse(base)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("OPENWA_BASE_URL must be an HTTP(S) gateway URL")
    session = quote(os.environ["OPENWA_SESSION_ID"], safe="")
    response = requests.post(
        f"{base}/api/sessions/{session}/messages/send-text",
        headers={"X-API-Key": os.environ["OPENWA_API_KEY"]},
        json={"chatId": chat, "text": text}, timeout=30, allow_redirects=False,
    )
    if not 200 <= response.status_code < 300:
        raise RuntimeError(f"OpenWA returned HTTP {response.status_code}")
    return response.json()["messageId"]
