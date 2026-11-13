"""Deterministic operator approvals; never infer permission from model output."""
import logging
import re
from contextlib import closing

from app.tools import whatsapp

SEND = re.compile(r"(?:please\s+)?(?:send|approve\s+and\s+send)\s+(?:whatsapp\s+)?draft\s*#?\s*([1-9][0-9]*)(?:\s+please)?[.!]?", re.I)
AMBIGUOUS = re.compile(r"(?:please\s+)?send\s+(?:it|this|that|the\s+(?:draft|reply)|(?:the\s+)?latest\s+(?:draft|reply))(?:\s+please)?[.!]?", re.I)


def operator_command(message):
    """Handle exact send commands before reasoning. None means no command matched."""
    text = message.strip()
    if AMBIGUOUS.fullmatch(text):
        return {"reply": "Which WhatsApp draft should I send? Specify its ID, for example: send draft #3.",
                "tool_calls": [], "tool_results": []}
    match = SEND.fullmatch(text)
    if not match:
        return None
    draft_id = int(match[1])
    call_id = "operator-send"
    calls = [{"name": "send_whatsapp_draft", "args": {"draft_id": draft_id}}]
    with closing(whatsapp.connect()) as db:
        try:
            # approve atomically claims the draft and enforces the test-chat boundary.
            whatsapp.approve(db, draft_id)
        except ValueError as exc:
            error = str(exc)
        except Exception:
            logging.getLogger(__name__).exception("Operator-approved WhatsApp send failed")
            error = "Send outcome uncertain. Inspect the draft and WhatsApp/OpenWA before retrying."
        else:
            row = dict(db.execute("SELECT * FROM drafts WHERE id=?", (draft_id,)).fetchone())
            return {"reply": f"Sent WhatsApp draft #{draft_id} to {row['chat']} (gateway accepted).",
                    "tool_calls": calls, "tool_results": [{"tool_call_id": call_id,
                        "content": {"ok": True, "result": row}}]}
    return {"reply": f"I couldn't send draft #{draft_id}: {error}", "tool_calls": calls,
            "tool_results": [{"tool_call_id": call_id, "content": {"ok": False, "error": error}}]}
