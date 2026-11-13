"""Database operations shared by the FastAPI UI endpoints."""

import json
import os
from datetime import datetime, timezone
from urllib.parse import unquote

import requests

from app.tools import whatsapp as bot
from app.services import cloudapi
from app.services.chat_policy import chat_scope, unrestricted
from app.services.messaging import provider


class APIError(Exception):
    def __init__(self, status, message):
        self.status, self.message = status, message


def encode_row(row):
    item = dict(row)
    if "details" in item:
        item["details"] = json.loads(item["details"])
    if "due" in item:
        item["due"] = datetime.fromtimestamp(item["due"], timezone.utc).isoformat()
    return item


def require_text(body, field):
    value = body.get(field)
    if not isinstance(value, str) or not value.strip():
        raise APIError(400, f"{field} must be a nonempty string")
    return value


def current_row(db, table, item_id):
    scope, params = chat_scope()
    row = db.execute(f"SELECT * FROM {table} WHERE id=? AND ({scope})", [item_id, *params]).fetchone()
    if row is None:
        raise APIError(404, "Item not found in the allowed test chat")
    return row


def connection_status():
    if provider() == "cloud":
        return {**cloudapi.status(), "provider": "cloud",
                "test_chat_id": os.getenv("OPENWA_TEST_CHAT_ID", "").strip() or None, "allow_all_chats": unrestricted()}
    try:
        response = requests.get(os.environ["OPENWA_BASE_URL"].rstrip("/") + "/api/sessions",
                                headers={"X-API-Key": os.environ["OPENWA_API_KEY"]},
                                timeout=8, allow_redirects=False)
        response.raise_for_status()
        sessions = response.json()
        if not isinstance(sessions, list):
            raise ValueError("Unexpected session list")
        session = next((x for x in sessions if isinstance(x, dict) and x.get("id") == os.getenv("OPENWA_SESSION_ID")), None)
        return {"gateway_reachable": True, "session_found": session is not None,
                "session_status": session.get("status") if session else None,
                "test_chat_id": os.getenv("OPENWA_TEST_CHAT_ID", "").strip() or None,
                "allow_all_chats": unrestricted()}
    except (requests.RequestException, ValueError, KeyError):
        return {"gateway_reachable": False, "session_found": None, "session_status": None,
                "test_chat_id": os.getenv("OPENWA_TEST_CHAT_ID", "").strip() or None,
                "allow_all_chats": unrestricted()}


def route(db, method, path, query, body):
    parts = [unquote(x) for x in path.strip("/").split("/")]
    chat = os.getenv("OPENWA_TEST_CHAT_ID", "").strip()
    if method == "GET" and parts == ["api", "status"]:
        return 200, connection_status()
    if method == "GET" and parts in (["api", "leads"], ["api", "drafts"], ["api", "reminders"]):
        table = parts[1]
        try:
            limit = int(query.get("limit", ["100"])[0])
            offset = int(query.get("offset", ["0"])[0])
        except ValueError:
            raise APIError(400, "limit and offset must be integers")
        if not 1 <= limit <= 500 or offset < 0:
            raise APIError(400, "limit must be 1..500 and offset must be nonnegative")
        where, params = chat_scope()
        if "state" in query:
            if table == "leads":
                raise APIError(400, "Leads do not have a state filter")
            where += " AND state=?"
            params.append(query["state"][0])
        total = db.execute(f"SELECT count(*) FROM {table} WHERE {where}", params).fetchone()[0]
        order = "updated_at DESC" if table == "leads" else "id DESC"
        rows = db.execute(f"SELECT * FROM {table} WHERE {where} ORDER BY {order} LIMIT ? OFFSET ?",
                          [*params, limit, offset]).fetchall()
        return 200, {"items": [encode_row(x) for x in rows], "total": total, "limit": limit, "offset": offset}
    if method == "GET" and len(parts) == 4 and parts[:2] == ["api", "leads"] and parts[3] == "messages":
        if not bot.allowed_chat(parts[2]):
            raise APIError(404, "Chat not found")
        chat = parts[2]
        try:
            limit = int(query.get("limit", ["100"])[0])
            offset = int(query.get("offset", ["0"])[0])
        except ValueError:
            raise APIError(400, "limit and offset must be integers")
        if not 1 <= limit <= 500 or offset < 0:
            raise APIError(400, "limit must be 1..500 and offset must be nonnegative")
        # Legacy rows have no timestamp; their original interleaving is unknown.
        messages = db.execute("""
            SELECT id,body AS text,'inbound' AS direction,state,created_at AS timestamp
            FROM inbox WHERE chat=?
            UNION ALL
            SELECT message_id AS id,text,'outbound' AS direction,state,sent_at AS timestamp
            FROM drafts WHERE chat=? AND state='sent'
            ORDER BY timestamp DESC,id DESC LIMIT ? OFFSET ?
        """, (chat, chat, limit, offset)).fetchall()
        total = db.execute("SELECT (SELECT count(*) FROM inbox WHERE chat=?) + (SELECT count(*) FROM drafts WHERE chat=? AND state='sent')", (chat, chat)).fetchone()[0]
        return 200, {"items": [dict(x) for x in messages], "total": total, "limit": limit, "offset": offset,
                     "manual_phone_replies_included": False}
    if len(parts) >= 3 and parts[:2] == ["api", "drafts"]:
        if not parts[2].isdigit():
            raise APIError(400, "Draft id must be an integer")
        item_id = int(parts[2])
        row = current_row(db, "drafts", item_id)
        if method == "GET" and len(parts) == 3:
            return 200, encode_row(row)
        if row["state"] != "draft":
            raise APIError(409, "Only a pending draft can be changed or approved")
        if method == "PATCH" and len(parts) == 3:
            text = require_text(body, "text")
            with db:
                count = db.execute("UPDATE drafts SET text=? WHERE id=? AND state='draft'", (text, item_id)).rowcount
        elif method == "POST" and len(parts) == 4 and parts[3] == "reject":
            with db:
                count = db.execute("UPDATE drafts SET state='rejected' WHERE id=? AND state='draft'", (item_id,)).rowcount
        elif method == "POST" and len(parts) == 4 and parts[3] == "approve":
            replacement = require_text(body, "text") if "text" in body else None
            try:
                bot.approve(db, item_id, replacement)
            except ValueError as exc:
                raise APIError(409, str(exc))
            except Exception:
                bot.LOG.exception("API approval send failed")
                raise APIError(502, "Send outcome uncertain. Inspect the chat/gateway before any manual retry.")
            count = 1
        else:
            raise APIError(404, "Unknown API endpoint")
        if not count:
            raise APIError(409, "Draft changed; refresh before trying again")
        return 200, encode_row(current_row(db, "drafts", item_id))
    if method == "POST" and parts == ["api", "reminders"]:
        lead = require_text(body, "chat")
        due = require_text(body, "at")
        note = require_text(body, "note")
        try:
            item_id = bot.add_reminder(db, lead, due, note)
        except ValueError as exc:
            raise APIError(400, str(exc))
        return 201, encode_row(current_row(db, "reminders", item_id))
    if method == "POST" and len(parts) == 4 and parts[:2] == ["api", "reminders"] and parts[3] == "cancel":
        if not parts[2].isdigit():
            raise APIError(400, "Reminder id must be an integer")
        item_id = int(parts[2])
        current_row(db, "reminders", item_id)
        with db:
            count = db.execute("UPDATE reminders SET state='cancelled' WHERE id=? AND state='pending'", (item_id,)).rowcount
        if not count:
            raise APIError(409, "Only a pending reminder can be cancelled")
        return 200, encode_row(current_row(db, "reminders", item_id))
    raise APIError(404, "Unknown API endpoint")
