"""Tools available to the operator-facing agent. Sending is approval-only."""
import json
import os
import uuid
from contextlib import closing
from pathlib import Path
from langchain_core.tools import tool
from app.tools import social, whatsapp
from app.services.chat_policy import chat_scope


@tool
def list_leads() -> list[dict]:
    """List saved lead facts in the configured test chat."""
    with closing(whatsapp.connect()) as db:
        scope, params = chat_scope()
        return [{**dict(row), "details": json.loads(row["details"])} for row in db.execute(
            f"SELECT * FROM leads WHERE {scope} ORDER BY updated_at DESC LIMIT 100", params)]


@tool
def read_conversation(chat: str) -> dict:
    """Read recent incoming messages and bot-sent replies for an allowed chat."""
    if not whatsapp.allowed_chat(chat):
        raise ValueError("Chat is outside the test restriction")
    with closing(whatsapp.connect()) as db:
        return {"incoming": [dict(x) for x in db.execute(
            "SELECT body,created_at FROM inbox WHERE chat=? ORDER BY rowid DESC LIMIT 30", (chat,))],
            "sent_replies": [dict(x) for x in db.execute(
                "SELECT text,sent_at FROM drafts WHERE chat=? AND state='sent' ORDER BY id DESC LIMIT 10", (chat,))],
            "manual_phone_replies_included": False}


@tool
def list_reply_drafts() -> list[dict]:
    """List the most recent WhatsApp drafts for the allowed test chat."""
    with closing(whatsapp.connect()) as db:
        scope, params = chat_scope()
        return [dict(x) for x in db.execute(f"SELECT * FROM drafts WHERE {scope} ORDER BY id DESC LIMIT 30", params)]


@tool
def draft_whatsapp_reply(chat: str) -> dict:
    """Generate and save a new reply draft for an existing lead. Does not send it."""
    if not whatsapp.allowed_chat(chat):
        raise ValueError("Chat is outside the test restriction")
    with closing(whatsapp.connect()) as db:
        if not db.execute("SELECT 1 FROM leads WHERE chat=?", (chat,)).fetchone():
            raise ValueError("Unknown lead")
        result = whatsapp.generate(db, chat)
        if not result.reply.strip():
            raise ValueError("Model returned an empty draft")
        with db:
            db.execute("UPDATE drafts SET state='superseded' WHERE chat=? AND state='draft'", (chat,))
            draft_id = db.execute("INSERT INTO drafts(event_id,chat,text) VALUES(?,?,?)",
                                  ("operator:" + str(uuid.uuid4()), chat, result.reply)).lastrowid
        return {"id": draft_id, "chat": chat, "text": result.reply, "state": "draft"}


@tool
def draft_social_post(platform: str, topic: str) -> dict:
    """Draft a company post for linkedin, x, or instagram and save it for approval."""
    if platform not in social.LIMITS:
        raise ValueError("Unsupported social platform")
    company = json.loads(Path("company.json").read_text(encoding="utf-8"))
    if not company.get("name") or not topic.strip():
        raise ValueError("Company name and topic are required")
    return social.build_social_workflow().invoke({"company": company, "topic": topic, "platform": platform})


@tool
def list_social_drafts() -> list[dict]:
    """List up to 50 saved social posts with their approval/submission status."""
    posts = []
    for path in sorted(Path("posts").glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:50]:
        item = json.loads(path.read_text(encoding="utf-8"))
        posts.append(item)
    return posts


@tool
def list_reminders() -> list[dict]:
    """List follow-up reminders for the configured test chat; due values are Unix seconds."""
    with closing(whatsapp.connect()) as db:
        scope, params = chat_scope()
        return [dict(x) for x in db.execute(f"SELECT * FROM reminders WHERE {scope} ORDER BY id DESC LIMIT 100", params)]


@tool
def create_reminder(chat: str, at: str, note: str) -> dict:
    """Save an owner follow-up reminder at an explicit future ISO datetime with timezone."""
    with closing(whatsapp.connect()) as db:
        return {"id": whatsapp.add_reminder(db, chat, at, note), "state": "pending"}


@tool
def cancel_reminder(reminder_id: int) -> dict:
    """Cancel a pending reminder for the configured test chat."""
    with closing(whatsapp.connect()) as db, db:
        scope, params = chat_scope()
        count = db.execute(f"UPDATE reminders SET state='cancelled' WHERE id=? AND ({scope}) AND state='pending'",
                           [reminder_id, *params]).rowcount
        if not count:
            raise ValueError("No pending reminder in the allowed chat")
    return {"id": reminder_id, "state": "cancelled"}


# Neither publishing nor WhatsApp send/approval is callable by the model.
TOOLS = [list_leads, read_conversation, list_reply_drafts, draft_whatsapp_reply,
         draft_social_post, list_social_drafts, list_reminders, create_reminder, cancel_reminder]
