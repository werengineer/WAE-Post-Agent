"""Lead manager logic: classify replies, update status, schedule follow-ups,
build reminders for the owner (Lokesh) and manager-style digests."""

import re
from datetime import datetime, timedelta, timezone

from . import store

STATUSES = ["new", "contacted", "replied", "interested", "meeting_booked",
            "not_interested", "won", "lost", "opted_out"]
OPEN = ("new", "contacted", "replied", "interested", "meeting_booked")

# Ordered: first match wins. English + common Hinglish phrases. Tune with real replies.
RULES = [
    ("opted_out", r"\b(stop|unsubscribe|do not contact|don'?t (message|contact)|remove me)\b"),
    ("not_interested", r"\b(not interested|no thanks?|no thank you|nahi chahiye|not now|nahi)\b"),
    ("meeting_booked", r"\b(book|schedule|call me|let'?s (talk|meet|connect)|demo|meeting)\b"),
    ("interested", r"\b(interested|price|pricing|cost|quote|details|tell me more|more info|kitna|rate)\b"),
]
FOLLOWUP_DAYS = {"replied": 1, "interested": 1, "meeting_booked": 1, "contacted": 3, "new": 1}

REPLY_TEMPLATES = {
    "interested": "Thanks for your interest{name}! Could you share a good time for a short call? "
                  "We'll walk you through the details.",
    "meeting_booked": "Great{name}! Lokesh will confirm a time with you shortly.",
    "not_interested": "No problem{name}, thanks for letting us know. Reach out anytime.",
    "opted_out": None,   # never reply to an opt-out
    "replied": "Thanks for your message{name}! Lokesh will get back to you shortly.",
}


def classify(text: str) -> str:
    t = text.lower()
    for status, pattern in RULES:
        if re.search(pattern, t):
            return status
    return "replied"


def handle_inbound(db, phone: str, name: str, text: str, wa_id: str | None = None) -> dict:
    lead = store.get_or_create_lead(db, phone, name)
    if not store.log_message(db, lead["id"], "in", text, wa_id):
        return {"duplicate": True}
    status = classify(text)
    db.execute("UPDATE leads SET last_inbound_at=? WHERE id=?", (store.now(), lead["id"]))
    if lead["status"] in ("won", "lost") and status == "replied":
        status = lead["status"]            # don't reopen closed leads on a plain reply
    store.set_status(db, lead["id"], status)
    if status == "opted_out":
        db.execute("UPDATE leads SET opted_out=1 WHERE id=?", (lead["id"],))
        db.execute("UPDATE followups SET done=1 WHERE lead_id=?", (lead["id"],))
        db.execute("UPDATE outbox SET status='cancelled' WHERE lead_id=? "
                   "AND status='pending_approval'", (lead["id"],))
        db.commit()
    elif status in FOLLOWUP_DAYS:
        due = (datetime.now(timezone.utc) + timedelta(days=FOLLOWUP_DAYS[status])).isoformat()
        store.add_followup(db, lead["id"], due, f"Lead {status}: \"{text[:80]}\"")
    else:
        db.execute("UPDATE followups SET done=1 WHERE lead_id=?", (lead["id"],))
        db.commit()
    tmpl = REPLY_TEMPLATES.get(status)
    outbox_id = None
    if tmpl and not lead["opted_out"]:
        first = (lead["name"] or name).split(" ")[0] if (lead["name"] or name) else ""
        outbox_id = store.queue_outbound(db, lead["id"], "lead_reply", lead["phone"],
                                         tmpl.format(name=f" {first}" if first else ""))
    return {"lead_id": lead["id"], "status": status, "outbox_id": outbox_id}


def due_reminders(db, mark: bool = False) -> str | None:
    """Reminder text for Lokesh listing overdue follow-ups, or None."""
    rows = db.execute(
        "SELECT f.id, f.reason, f.due_at, l.name, l.phone, l.status FROM followups f "
        "JOIN leads l ON l.id=f.lead_id WHERE f.done=0 AND l.opted_out=0 AND f.due_at<=? "
        "ORDER BY f.due_at", (store.now(),)).fetchall()
    if not rows:
        return None
    lines = ["Lokesh, follow-ups due:"]
    for r in rows:
        lines.append(f"- {r['name'] or '+' + r['phone']} ({r['status']}): {r['reason']}")
    if mark:
        for r in rows:
            db.execute("UPDATE followups SET reminded_at=? WHERE id=?", (store.now(), r["id"]))
        db.commit()
    return "\n".join(lines)


def digest(db, hours: int = 24) -> str:
    since = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    counts = {s: n for s, n in db.execute("SELECT status, COUNT(*) FROM leads GROUP BY status")}
    new_in = db.execute("SELECT COUNT(*) FROM leads WHERE created_at>=?", (since,)).fetchone()[0]
    replies = db.execute("SELECT COUNT(*) FROM messages WHERE direction='in' AND created_at>=?",
                         (since,)).fetchone()[0]
    overdue = db.execute("SELECT COUNT(*) FROM followups f JOIN leads l ON l.id=f.lead_id "
                         "WHERE f.done=0 AND l.opted_out=0 AND f.due_at<=?", (store.now(),)).fetchone()[0]
    hot = db.execute("SELECT name, phone, status FROM leads WHERE status IN "
                     "('interested','meeting_booked') ORDER BY updated_at DESC LIMIT 5").fetchall()
    pending = db.execute("SELECT COUNT(*) FROM outbox WHERE status='pending_approval'").fetchone()[0]
    lines = [f"Lead update (last {hours}h)",
             f"New leads: {new_in} | Replies received: {replies} | Overdue follow-ups: {overdue}",
             "Pipeline: " + (", ".join(f"{s} {counts[s]}" for s in STATUSES if s in counts) or "empty")]
    if hot:
        lines.append("Hot leads: " + "; ".join(f"{h['name'] or '+' + h['phone']} ({h['status']})" for h in hot))
    if pending:
        lines.append(f"Messages awaiting approval: {pending}")
    return "\n".join(lines)
