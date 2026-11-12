"""Picks the WhatsApp transport. WHATSAPP_PROVIDER=cloud uses Meta's official WhatsApp Cloud API;
anything else (the default) keeps the OpenWA gateway exactly as before."""
import os


def provider():
    return "cloud" if os.getenv("WHATSAPP_PROVIDER", "openwa").strip().lower() == "cloud" else "openwa"


def session_id():
    """The id incoming events must carry: the business number's id (cloud) or the OpenWA session id."""
    return os.environ["WHATSAPP_PHONE_NUMBER_ID" if provider() == "cloud" else "OPENWA_SESSION_ID"]


def send_text(chat, text):
    if provider() == "cloud":
        from app.services import cloudapi
        return cloudapi.send_text(chat, text)
    from app.services import openwa
    return openwa.send_text(chat, text)
