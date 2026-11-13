"""SQLite schema and compatibility migrations."""
import os
import sqlite3


def connect():
    db = sqlite3.connect(os.getenv("WHATSAPP_DB", "whatsapp.sqlite3"), timeout=30)
    db.row_factory = sqlite3.Row
    db.executescript("""
        CREATE TABLE IF NOT EXISTS inbox (
            id TEXT PRIMARY KEY, chat TEXT NOT NULL, body TEXT NOT NULL,
            state TEXT NOT NULL DEFAULT 'pending', attempts INTEGER NOT NULL DEFAULT 0,
            retry_at REAL NOT NULL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS leads (
            chat TEXT PRIMARY KEY, details TEXT NOT NULL, updated_at REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS drafts (
            id INTEGER PRIMARY KEY, event_id TEXT UNIQUE NOT NULL, chat TEXT NOT NULL,
            text TEXT NOT NULL, state TEXT NOT NULL DEFAULT 'draft', message_id TEXT);
        CREATE TABLE IF NOT EXISTS reminders (
            id INTEGER PRIMARY KEY, chat TEXT NOT NULL, due REAL NOT NULL,
            note TEXT NOT NULL, state TEXT NOT NULL DEFAULT 'pending');
        CREATE TABLE IF NOT EXISTS notices (
            id INTEGER PRIMARY KEY, text TEXT NOT NULL,
            state TEXT NOT NULL DEFAULT 'pending', chat TEXT);
    """)
    if "chat" not in {row["name"] for row in db.execute("PRAGMA table_info(notices)")}:
        with db:
            db.execute("ALTER TABLE notices ADD COLUMN chat TEXT")
    for table, column in (("inbox", "created_at"), ("drafts", "sent_at")):
        if column not in {row["name"] for row in db.execute(f"PRAGMA table_info({table})")}:
            with db:
                db.execute(f"ALTER TABLE {table} ADD COLUMN {column} REAL")
    return db
