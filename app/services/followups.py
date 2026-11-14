"""Automatic follow-ups: a customer who got our reply and then went quiet gets one polite nudge.

Switched on with FOLLOWUP=on (OpenWA mode only). Rules, all enforced here and not by the model:
  - only after a reply WE sent to a lead (the follow-up is planned when that reply goes out), never a cold message;
  - FOLLOWUP_DELAYS_HOURS (default "24"): hours after our reply for the first follow-up; "24,72" adds a second one 72 hours after the first;
  - any new message from the customer cancels what is waiting (they answered); a stop / not-interested message
    ("stop", "not interested", "nahi chahiye", "mat bhejo" ...) blocks every future follow-up to that chat;
  - only inside FOLLOWUP_HOURS (default "10-19", in AGENT_TIMEZONE); a follow-up that comes due at night waits for the morning;
  - FOLLOWUP_MAX_PER_DAY (default 200) in total; individual chats that the chat policy allows, never groups;
  - a send that fails or times out is marked "uncertain" and is never repeated; the owner is told about every follow-up that was sent.
The text is written by the model from the whole conversation, in the customer's language (see app/agent/drafting.py).
"""
import logging
import os
import re
import time
from datetime import datetime
from zoneinfo import ZoneInfo

from app.services.chat_policy import allowed_chat
from app.services.messaging import provider, send_text

LOG = logging.getLogger(__name__)
MAX_ATTEMPTS = 5          # text generation that keeps failing is given up after this many tries
RETRY_SECONDS = 600       # ... and tried again after this long

# a customer who says no must not hear from us again (English, Hinglish, Hindi). A false alarm only costs a follow-up, so the net is wide.
OPT_OUT = re.compile(
    r"\b(stop|unsubscribe|opt[ -]?out|spam|remove me|do not (message|contact|text|call)|don'?t (message|contact|text|call)|not interested|no thanks?|no thank you"
    r"|interested nahi|nahi chahiye|nahin chahiye|zarurat nahi|jarurat nahi|mat (bhejo|karo)|message (mat|band)|band karo|pareshan mat)\b"
    r"|नहीं चाहिए|मत भेजो|मैसेज मत|स्टॉप|परेशान मत",
    re.IGNORECASE,
)


def enabled():
    # on a Meta Cloud API number a free text only works inside 24 hours of the customer's last message: a 24-hour follow-up would be refused
    return os.getenv("FOLLOWUP", "off").strip().lower() == "on" and provider() == "openwa"


def delays():
    hours = []
    for part in os.getenv("FOLLOWUP_DELAYS_HOURS", "24").split(","):
        try:
            value = float(part.strip())
        except ValueError:
            continue
        if value > 0:
            hours.append(value)
    return hours or [24.0]


def in_hours(now=None, requested=False):
    """Inside the sending window? A time the customer asked for has its own, wider window (FOLLOWUP_REQUESTED_HOURS, default 8-21)."""
    default = "8-21" if requested else "10-19"
    match = re.fullmatch(r"\s*(\d{1,2})\s*-\s*(\d{1,2})\s*", os.getenv("FOLLOWUP_REQUESTED_HOURS" if requested else "FOLLOWUP_HOURS", default))
    fallback = (8, 21) if requested else (10, 19)
    start, end = (int(match[1]), int(match[2])) if match else fallback
    if not 0 <= start < end <= 24:
        start, end = fallback
    now = now or datetime.now(ZoneInfo(os.getenv("AGENT_TIMEZONE", "Asia/Kolkata")))
    return start <= now.hour < end


def _daily_limit():
    try:
        return max(0, int(os.getenv("FOLLOWUP_MAX_PER_DAY", "").strip() or 200))
    except ValueError:
        return 200


def is_opted_out(db, chat):
    return db.execute("SELECT 1 FROM optouts WHERE chat=?", (chat,)).fetchone() is not None


def requested_time(text, now=None):
    """The moment the customer asked for ("shaam ko 6 baje"), as the model wrote it in ISO 8601 -> epoch seconds, or None when it is empty,
    unreadable, in the past or more than 30 days away. A time without an offset is read in AGENT_TIMEZONE."""
    if not isinstance(text, str) or not text.strip():
        return None
    try:
        moment = datetime.fromisoformat(text.strip())
    except ValueError:
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=ZoneInfo(os.getenv("AGENT_TIMEZONE", "Asia/Kolkata")))
    now = now if now is not None else time.time()
    stamp = moment.timestamp()
    return stamp if now + 60 <= stamp <= now + 30 * 86400 else None


def schedule(db, chat, draft_id=None, requested_at=None):
    """Called when a reply to a lead has been sent: plan the first follow-up (unless one is already waiting).
    requested_at = the time the customer asked us to get back to them: it replaces the usual delay."""
    if not enabled() or not isinstance(chat, str) or chat.endswith("@g.us") or is_opted_out(db, chat):
        return False
    if db.execute("SELECT 1 FROM followups WHERE chat=? AND state IN ('pending','sending')", (chat,)).fetchone():
        return False
    now = time.time()
    # the asked-for moment was checked when the reply was written; if it has slipped into the past meanwhile (late approval), the normal delay applies
    asked = float(requested_at) if requested_at and now + 60 <= float(requested_at) <= now + 30 * 86400 else None
    with db:
        db.execute("INSERT INTO followups(chat,step,due,created_at,draft_id,requested) VALUES(?,?,?,?,?,?)",
                   (chat, 1, asked if asked else now + delays()[0] * 3600, now, draft_id, 1 if asked else 0))
        if asked:
            local = datetime.fromtimestamp(asked, ZoneInfo(os.getenv("AGENT_TIMEZONE", "Asia/Kolkata"))).strftime("%d %b, %I:%M %p")
            _notice(db, chat, f"{chat} asked us to get back to them: follow-up planned for {local}.")
    return True


def register_inbound(db, chat, text):
    """Called inside the transaction that stores a NEW customer message: they answered, so nothing waits any more; "stop" blocks the chat."""
    db.execute("UPDATE followups SET state='cancelled' WHERE chat=? AND state='pending'", (chat,))
    if isinstance(text, str) and OPT_OUT.search(text):
        db.execute("INSERT OR REPLACE INTO optouts(chat,at,reason) VALUES(?,?,?)", (chat, time.time(), text[:80]))


def _notice(db, chat, text):
    db.execute("INSERT INTO notices(text,chat) VALUES(?,?)", (text, chat))


def tick(db, now=None):
    """One look (the worker calls it every few seconds): send at most ONE due follow-up."""
    if not enabled():
        return
    now = now if now is not None else time.time()
    row = db.execute("SELECT * FROM followups WHERE state='pending' AND due<=? ORDER BY due LIMIT 1", (now,)).fetchone()
    if not row:
        return
    chat = row["chat"]
    if is_opted_out(db, chat) or not allowed_chat(chat) or chat.endswith("@g.us"):
        with db:
            db.execute("UPDATE followups SET state='cancelled' WHERE id=?", (row["id"],))
        return
    if not in_hours(requested=bool(row["requested"])):
        return  # it stays due and goes out when the window opens
    sent_today = db.execute("SELECT count(*) FROM followups WHERE state='sent' AND sent_at>?", (now - 86400,)).fetchone()[0]
    if sent_today >= _daily_limit():
        return
    with db:  # claim it before anything is sent: a crash from here on can never lead to a second message
        if not db.execute("UPDATE followups SET state='sending' WHERE id=? AND state='pending'", (row["id"],)).rowcount:
            return
    try:
        from app.agent.drafting import generate_followup
        text = (generate_followup(db, chat, row["step"], bool(row["requested"])) or "").strip()
    except Exception:
        LOG.exception("Follow-up text could not be written")
        attempts = row["attempts"] + 1
        with db:
            if attempts >= MAX_ATTEMPTS:
                db.execute("UPDATE followups SET state='failed', attempts=? WHERE id=?", (attempts, row["id"]))
            else:
                db.execute("UPDATE followups SET state='pending', attempts=?, due=? WHERE id=?", (attempts, now + RETRY_SECONDS, row["id"]))
        return
    if not text:  # the model found nothing to say (customer asked to stop, or the talk is over)
        with db:
            db.execute("UPDATE followups SET state='cancelled' WHERE id=?", (row["id"],))
        return
    try:
        message_id = send_text(chat, text)
    except Exception:
        LOG.exception("Follow-up send is uncertain; inspect WhatsApp before sending anything to this customer")
        with db:
            db.execute("UPDATE followups SET state='uncertain', text=? WHERE id=?", (text, row["id"]))
            _notice(db, chat, f"A follow-up to {chat} may or may not have been sent (marked uncertain, it will not be repeated). Check WhatsApp.")
        return
    sent_at = time.time()
    with db:
        db.execute("UPDATE followups SET state='sent', text=?, message_id=?, sent_at=? WHERE id=?", (text, message_id, sent_at, row["id"]))
        _notice(db, chat, f"Follow-up #{row['step']} sent to {chat}:\n{text}")
        plan = delays()
        if row["step"] < len(plan):  # the next follow-up counts from this one
            db.execute("INSERT INTO followups(chat,step,due,created_at,draft_id) VALUES(?,?,?,?,?)",
                       (chat, row["step"] + 1, sent_at + plan[row["step"]] * 3600, sent_at, row["draft_id"]))
