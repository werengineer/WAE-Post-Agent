"""Shared chat access policy for ingestion, tools, and the UI API."""
import os


def unrestricted():
    return os.getenv("OPENWA_ALLOW_ALL_CHATS", "false").strip().lower() == "true"


def groups_allowed():
    return os.getenv("OPENWA_ALLOW_GROUPS", "false").strip().lower() == "true"


def allowed_chat(chat):
    if not isinstance(chat, str) or not chat.endswith(("@c.us", "@s.whatsapp.net", "@lid", "@g.us")):
        return False
    if unrestricted():
        # "every customer" means every person who writes to the number: the linked phone is usually in many groups, which stay out
        # unless OPENWA_ALLOW_GROUPS=true. (A group chosen as THE test chat below still works.)
        return not chat.endswith("@g.us") or groups_allowed()
    return chat == os.getenv("OPENWA_TEST_CHAT_ID", "").strip()


def chat_scope():
    if unrestricted():
        return "1=1", []
    return "chat=?", [os.getenv("OPENWA_TEST_CHAT_ID", "").strip()]
