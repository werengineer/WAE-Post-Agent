"""WhatsApp lead, draft, and reminder operations; never auto-approve a reply."""
import json
import logging
import os
import time
from datetime import datetime
from app.storage.database import connect
from app.services.messaging import send_text, session_id
from app.agent.drafting import LeadDraft, generate
from app.services.chat_policy import allowed_chat
from app.services import followups

LOG = logging.getLogger(__name__)


def accept(db, event):
    if not isinstance(event, dict):
        raise ValueError("Expected an event object")
    if event.get("sessionId") != session_id():
        raise ValueError("Unexpected session")
    if event.get("event") != "message.received":
        return False
    data = event.get("data", {})
    if not isinstance(data, dict):
        raise ValueError("Expected message data")
    chat = data.get("chatId") or data.get("from")
    body = data.get("body")
    if (data.get("fromMe") is not False
            or not isinstance(chat, str) or not chat.endswith(("@c.us", "@s.whatsapp.net", "@lid", "@g.us"))
            or (data.get("isGroup") and not chat.endswith("@g.us"))
            or not allowed_chat(chat)
            or not isinstance(body, str) or not body.strip()):
        return False
    message_id = data.get("id")
    if not isinstance(message_id, str) or not message_id:
        raise ValueError("Message id required")
    if chat.endswith("@g.us"):
        body = json.dumps({"sender": data.get("author"), "text": body}, ensure_ascii=False)
    # A message delivered via multiple webhook subscriptions is still one message.
    key = event["sessionId"] + ":" + message_id
    with db:
        inserted = db.execute("INSERT OR IGNORE INTO inbox(id,chat,body,created_at) VALUES(?,?,?,?)",
                              (key, chat, body, time.time())).rowcount
        if inserted:
            # Do not send a stale reply or follow-up after a new customer message.
            db.execute("UPDATE drafts SET state='superseded' WHERE chat=? AND state='draft'", (chat,))
            db.execute("UPDATE reminders SET state='cancelled' WHERE chat=? AND state='pending'", (chat,))
            # the customer answered: a waiting follow-up is cancelled, and "stop" blocks the chat for good
            followups.register_inbound(db, chat, body)
    return bool(inserted)

def auto_reply_on():
    return os.getenv("AUTO_REPLY", "off").strip().lower() == "on"


def _limit(name, default):
    try:
        return max(0, int(os.getenv(name, "").strip() or default))
    except ValueError:
        return default


def auto_reply_allowed(db, chat):
    """Automatic sending is opt-in (AUTO_REPLY=on), for individual chats only, and capped per chat and per day.
    When it is not allowed the reply simply stays a draft for a person."""
    if not auto_reply_on() or not chat.endswith(("@c.us", "@s.whatsapp.net", "@lid")):
        return False
    now = time.time()
    in_chat = db.execute("SELECT count(*) FROM drafts WHERE chat=? AND state='sent' AND sent_at>?", (chat, now - 3600)).fetchone()[0]
    in_day = db.execute("SELECT count(*) FROM drafts WHERE state='sent' AND sent_at>?", (now - 86400,)).fetchone()[0]
    return in_chat < _limit("AUTO_REPLY_MAX_PER_CHAT_HOUR", 6) and in_day < _limit("AUTO_REPLY_MAX_PER_DAY", 1000)


def process_one(db):
    row = db.execute("SELECT * FROM inbox WHERE state='pending' AND retry_at<=? ORDER BY rowid LIMIT 1",
                     (time.time(),)).fetchone()
    if not row:
        return
    if not allowed_chat(row["chat"]):
        with db:
            db.execute("UPDATE inbox SET state='ignored' WHERE id=?", (row["id"],))
        return
    draft_id = None  # set when this message produced a reply that may be sent automatically
    try:
        result = generate(db, row["chat"])
        with db:
            # Newer queued messages will produce their own draft with full history.
            newer = db.execute("SELECT 1 FROM inbox WHERE chat=? AND rowid>(SELECT rowid FROM inbox WHERE id=?)",
                               (row["chat"], row["id"])).fetchone()
            if result.is_lead:
                db.execute("INSERT INTO leads VALUES(?,?,?) ON CONFLICT(chat) DO UPDATE SET details=excluded.details, updated_at=excluded.updated_at",
                           (row["chat"], json.dumps(result.details), time.time()))
                if not newer:
                    if not result.reply.strip():
                        raise ValueError("Model returned an empty reply")
                    db.execute("UPDATE drafts SET state='superseded' WHERE chat=? AND state='draft'", (row["chat"],))
                    cursor = db.execute("INSERT INTO drafts(event_id,chat,text) VALUES(?,?,?)",
                                        (row["id"], row["chat"], result.reply))
                    if auto_reply_allowed(db, row["chat"]):
                        draft_id = cursor.lastrowid
                        footer = "Sent to the customer automatically."
                    else:
                        footer = "Review with: python -m app drafts"
                    db.execute("INSERT INTO notices(text,chat) VALUES(?,?)", (
                        f"Lead: {row['chat']}\nDetails: {json.dumps(result.details, ensure_ascii=False)}\n"
                        f"Draft #{cursor.lastrowid}:\n{result.reply}\n{footer}",
                        row["chat"],
                    ))
            db.execute("UPDATE inbox SET state='done' WHERE id=?", (row["id"],))
    except Exception:
        with db:
            db.execute("UPDATE inbox SET attempts=attempts+1,retry_at=? WHERE id=?", (time.time() + 60, row["id"]))
        LOG.exception("Draft generation failed; queued for retry")
    else:
        # Outside the try: a failed send must never re-run the model (that would draft and send a second reply).
        if draft_id is not None:
            try:
                approve(db, draft_id)
            except Exception:
                LOG.exception("Automatic reply failed; it is marked uncertain and is not resent")
                with db:
                    db.execute("INSERT INTO notices(text,chat) VALUES(?,?)", (
                        f"Automatic reply to {row['chat']} failed (draft #{draft_id} is marked uncertain). "
                        "Check WhatsApp before sending anything to this customer again.", row["chat"]))


def deliver(db, table, row, text):
    if not allowed_chat(row["chat"]):
        with db:
            db.execute(f"UPDATE {table} SET state='blocked' WHERE id=? AND state='pending'", (row["id"],))
        return
    # Claim before sending. A timeout/crash is ambiguous and must not cause duplicate sends.
    with db:
        claimed = db.execute(f"UPDATE {table} SET state='sending' WHERE id=? AND state='pending'", (row["id"],)).rowcount
    if not claimed:
        return
    try:
        send_text(os.environ["OPENWA_OWNER_CHAT_ID"], text)
    except Exception:
        with db:
            db.execute(f"UPDATE {table} SET state='uncertain' WHERE id=?", (row["id"],))
        LOG.exception("Owner notification uncertain; inspect gateway before retrying")
    else:
        with db:
            db.execute(f"UPDATE {table} SET state='sent' WHERE id=?", (row["id"],))


def tick(db):
    from app.services.scheduler import tick as scheduler_tick
    return scheduler_tick(db)


def approve(db, draft_id, replacement=None):
    with db:
        row = db.execute("SELECT * FROM drafts WHERE id=? AND state='draft'", (draft_id,)).fetchone()
        if not row:
            raise ValueError("No pending draft with this id")
        if not allowed_chat(row["chat"]):
            raise ValueError("This draft is outside the allowed test chat")
        text = replacement if replacement is not None else row["text"]
        if not text.strip():
            raise ValueError("Reply cannot be empty")
        if not db.execute("UPDATE drafts SET state='sending',text=? WHERE id=? AND state='draft'", (text, draft_id)).rowcount:
            raise ValueError("Draft already claimed")
    try:
        message_id = send_text(row["chat"], text)
    except Exception:
        with db:
            db.execute("UPDATE drafts SET state='uncertain' WHERE id=?", (draft_id,))
        raise
    with db:
        db.execute("UPDATE drafts SET state='sent',message_id=?,sent_at=? WHERE id=?", (message_id, time.time(), draft_id))
    try:
        followups.schedule(db, row["chat"], draft_id)  # FOLLOWUP=on: a nudge is planned after this reply
    except Exception:
        LOG.exception("Could not plan the follow-up; the reply itself was sent")


def add_reminder(db, chat, due, note):
    if not allowed_chat(chat):
        raise ValueError("This lead is outside the allowed test chat")
    when = datetime.fromisoformat(due)
    if when.tzinfo is None or when.utcoffset() is None:
        raise ValueError("Include a timezone offset, e.g. +05:30")
    if when.timestamp() <= time.time():
        raise ValueError("Reminder must be in the future")
    if not note.strip():
        raise ValueError("Reminder note cannot be empty")
    if not db.execute("SELECT 1 FROM leads WHERE chat=?", (chat,)).fetchone():
        raise ValueError("Unknown lead chat")
    with db:
        return db.execute("INSERT INTO reminders(chat,due,note) VALUES(?,?,?)", (chat, when.timestamp(), note)).lastrowid
