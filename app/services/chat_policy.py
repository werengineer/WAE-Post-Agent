"""Shared chat access policy for ingestion, tools, and the UI API."""
import os


def unrestricted():
    return os.getenv("OPENWA_ALLOW_ALL_CHATS", "false").strip().lower() == "true"


def allowed_chat(chat):
    if not isinstance(chat, str) or not chat.endswith(("@c.us", "@s.whatsapp.net", "@lid", "@g.us")):
        return False
    return unrestricted() or chat == os.getenv("OPENWA_TEST_CHAT_ID", "").strip()


def chat_scope():
    if unrestricted():
        return "1=1", []
    return "chat=?", [os.getenv("OPENWA_TEST_CHAT_ID", "").strip()]
