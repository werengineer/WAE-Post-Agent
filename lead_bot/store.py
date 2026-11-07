"""SQLite storage for leads, messages, follow-ups and the outbound queue."""

import sqlite3
from datetime import datetime, timezone

SCHEMA = """
CREATE TABLE IF NOT EXISTS leads (
  id INTEGER PRIMARY KEY, phone TEXT UNIQUE NOT NULL, name TEXT DEFAULT '',
  status TEXT NOT NULL DEFAULT 'new', owner TEXT DEFAULT 'Lokesh',
  opted_out INTEGER NOT NULL DEFAULT 0, notes TEXT DEFAULT '',
  created_at TEXT NOT NULL, updated_at TEXT NOT NULL, last_inbound_at TEXT);
CREATE TABLE IF NOT EXISTS messages (
  id INTEGER PRIMARY KEY, lead_id INTEGER NOT NULL, direction TEXT NOT NULL,
  body TEXT NOT NULL, wa_message_id TEXT UNIQUE, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS followups (
  id INTEGER PRIMARY KEY, lead_id INTEGER NOT NULL, due_at TEXT NOT NULL,
  reason TEXT NOT NULL, done INTEGER NOT NULL DEFAULT 0, reminded_at TEXT);
CREATE TABLE IF NOT EXISTS outbox (
  id INTEGER PRIMARY KEY, lead_id INTEGER, kind TEXT NOT NULL, recipient TEXT NOT NULL,
  body TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending_approval',
  created_at TEXT NOT NULL, sent_at TEXT, error TEXT);
"""


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def connect(path: str = "leads.db") -> sqlite3.Connection:
    db = sqlite3.connect(path)
    db.row_factory = sqlite3.Row
    db.executescript(SCHEMA)
    return db


def get_or_create_lead(db, phone: str, name: str = "") -> sqlite3.Row:
    phone = "".join(c for c in phone if c.isdigit())
    if not phone:
        raise ValueError("Phone number required (digits, with country code)")
    row = db.execute("SELECT * FROM leads WHERE phone=?", (phone,)).fetchone()
    if row is None:
        t = now()
        db.execute("INSERT INTO leads(phone,name,created_at,updated_at) VALUES(?,?,?,?)",
                   (phone, name, t, t))
        db.commit()
        row = db.execute("SELECT * FROM leads WHERE phone=?", (phone,)).fetchone()
    elif name and not row["name"]:
        db.execute("UPDATE leads SET name=? WHERE id=?", (name, row["id"]))
        db.commit()
    return row


def set_status(db, lead_id: int, status: str) -> None:
    db.execute("UPDATE leads SET status=?, updated_at=? WHERE id=?", (status, now(), lead_id))
    db.commit()


def log_message(db, lead_id: int, direction: str, body: str, wa_id: str | None = None) -> bool:
    """Returns False if this WhatsApp message id was already stored (webhook retry)."""
    try:
        db.execute("INSERT INTO messages(lead_id,direction,body,wa_message_id,created_at) "
                   "VALUES(?,?,?,?,?)", (lead_id, direction, body, wa_id, now()))
    except sqlite3.IntegrityError:
        return False
    db.commit()
    return True


def add_followup(db, lead_id: int, due_at: str, reason: str) -> None:
    # one open follow-up per lead: replace instead of piling up
    db.execute("UPDATE followups SET done=1 WHERE lead_id=? AND done=0", (lead_id,))
    db.execute("INSERT INTO followups(lead_id,due_at,reason) VALUES(?,?,?)",
               (lead_id, due_at, reason))
    db.commit()


def queue_outbound(db, lead_id, kind: str, recipient: str, body: str) -> int:
    cur = db.execute("INSERT INTO outbox(lead_id,kind,recipient,body,created_at) VALUES(?,?,?,?,?)",
                     (lead_id, kind, recipient, body, now()))
    db.commit()
    return cur.lastrowid
