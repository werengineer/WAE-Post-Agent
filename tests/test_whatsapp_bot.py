import hashlib
import hmac
import json
import os
import tempfile
import unittest
from contextlib import closing
from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient
from app.api.main import create_app
from pathlib import Path
from unittest.mock import patch

import requests

from app.tools import whatsapp as bot


class WhatsAppTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {
            "WHATSAPP_DB": str(Path(self.directory.name) / "test.sqlite3"),
            "OPENWA_SESSION_ID": "session", "OPENWA_OWNER_CHAT_ID": "owner@c.us",
            "OPENWA_WEBHOOK_SECRET": "a-long-test-secret",
            "OPENWA_ALLOW_ALL_CHATS": "false", "OPENWA_TEST_CHAT_ID": "customer@c.us",
        })
        self.env.start()
        self.db = bot.connect()
        self.event = {"sessionId": "session", "event": "message.received", "data": {
            "id": "msg1", "chatId": "customer@c.us", "body": "Need 10 purifiers in Delhi",
            "fromMe": False, "isGroup": False,
        }}

    def tearDown(self):
        self.db.close()
        self.env.stop()
        self.directory.cleanup()

    def test_duplicate_and_non_customer_messages(self):
        self.assertTrue(bot.accept(self.db, self.event))
        self.assertFalse(bot.accept(self.db, self.event))
        for change in ({"fromMe": True}, {"isGroup": True}, {"chatId": "owner@c.us"}):
            event = {**self.event, "data": {**self.event["data"], "id": "other", **change}}
            self.assertFalse(bot.accept(self.db, event))
        self.assertEqual(self.db.execute("SELECT count(*) FROM inbox").fetchone()[0], 1)

    def test_single_chat_filter_and_fail_closed(self):
        other = {**self.event, "data": {**self.event["data"], "chatId": "other@c.us"}}
        self.assertFalse(bot.accept(self.db, other))
        with patch.dict(os.environ, {"OPENWA_ALLOW_ALL_CHATS": "false", "OPENWA_TEST_CHAT_ID": ""}):
            self.assertFalse(bot.accept(self.db, self.event))
        self.assertEqual(self.db.execute("SELECT count(*) FROM inbox").fetchone()[0], 0)

    def test_unrestricted_mode_accepts_other_chats_but_ignores_outgoing(self):
        with patch.dict(os.environ, {"OPENWA_ALLOW_ALL_CHATS": "true"}):
            for chat in ("other@lid", "other@g.us"):
                event = {**self.event, "data": {**self.event["data"], "chatId": chat, "id": chat,
                         "isGroup": chat.endswith("@g.us")}}
                self.assertTrue(bot.accept(self.db, event))
                event["data"]["fromMe"] = True
                event["data"]["id"] += "-own"
                self.assertFalse(bot.accept(self.db, event))
        self.assertFalse(bot.allowed_chat("other@lid"))

    def test_only_selected_group_is_accepted_and_author_preserved(self):
        group = "120363405189874238@g.us"
        event = {**self.event, "data": {**self.event["data"], "chatId": group,
                 "isGroup": True, "author": "member@c.us"}}
        with patch.dict(os.environ, {"OPENWA_ALLOW_ALL_CHATS": "false", "OPENWA_TEST_CHAT_ID": group}):
            self.assertTrue(bot.accept(self.db, event))
            self.assertFalse(bot.accept(self.db, self.event))
            other = {**event, "data": {**event["data"], "chatId": "other@g.us"}}
            self.assertFalse(bot.accept(self.db, other))
            own = {**event, "data": {**event["data"], "id": "own", "fromMe": True}}
            self.assertFalse(bot.accept(self.db, own))
        stored = json.loads(self.db.execute("SELECT body FROM inbox").fetchone()[0])
        self.assertEqual(stored["sender"], "member@c.us")
        with patch.object(bot, "send_text", return_value="group-reply") as send:
            with self.db:
                self.db.execute("INSERT INTO drafts(event_id,chat,text) VALUES(?,?,?)", ("group-draft", group, "Reviewed group reply"))
            with patch.dict(os.environ, {"OPENWA_ALLOW_ALL_CHATS": "false", "OPENWA_TEST_CHAT_ID": group}):
                bot.approve(self.db, 1)
            send.assert_called_once_with(group, "Reviewed group reply")

    def test_existing_drafts_queue_and_notifications_cannot_bypass_filter(self):
        draft_id = self.draft()
        self.event["data"]["id"] = "queued"
        bot.accept(self.db, self.event)
        # Restore a pending draft to exercise the outbound guard independently.
        with self.db:
            self.db.execute("INSERT INTO reminders(chat,due,note) VALUES(?,?,?)", ("customer@c.us", 0, "Call"))
            self.db.execute("UPDATE drafts SET state='draft' WHERE id=?", (draft_id,))
        with patch.dict(os.environ, {"OPENWA_ALLOW_ALL_CHATS": "false", "OPENWA_TEST_CHAT_ID": "different@c.us"}), patch.object(bot, "send_text") as send, patch.object(bot, "generate") as model:
            with self.assertRaises(ValueError):
                bot.approve(self.db, draft_id)
            bot.tick(self.db)
            send.assert_not_called()
            model.assert_not_called()
        self.assertEqual(self.db.execute("SELECT state FROM reminders").fetchone()[0], "blocked")

    def test_owner_can_be_explicitly_selected_as_test_sender(self):
        with patch.dict(os.environ, {"OPENWA_OWNER_CHAT_ID": "customer@c.us"}):
            self.assertTrue(bot.accept(self.db, self.event))

    def draft(self):
        bot.accept(self.db, self.event)
        result = bot.LeadDraft(is_lead=True, details={"quantity": "10", "location": "Delhi"}, reply="What is your office size?")
        with patch.object(bot, "generate", return_value=result), patch.object(bot, "send_text") as send:
            bot.process_one(self.db)
            send.assert_not_called()
        return self.db.execute("SELECT id FROM drafts").fetchone()[0]

    def test_approval_and_duplicate_guard(self):
        draft_id = self.draft()
        with patch.object(bot, "send_text", return_value="wa-message") as send:
            bot.approve(self.db, draft_id, "Reviewed reply")
            send.assert_called_once_with("customer@c.us", "Reviewed reply")
            with self.assertRaises(ValueError):
                bot.approve(self.db, draft_id)

    def test_uncertain_send_is_not_retried(self):
        draft_id = self.draft()
        with patch.object(bot, "send_text", side_effect=requests.Timeout):
            with self.assertRaises(requests.Timeout):
                bot.approve(self.db, draft_id)
        self.assertEqual(self.db.execute("SELECT state FROM drafts").fetchone()[0], "uncertain")
        with self.assertRaises(ValueError):
            bot.approve(self.db, draft_id)

    def test_reminder_persistence_and_new_message_cancellation(self):
        self.draft()
        future = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
        reminder = bot.add_reminder(self.db, "customer@c.us", future, "Call customer")
        with closing(bot.connect()) as other:
            self.assertEqual(other.execute("SELECT state FROM reminders WHERE id=?", (reminder,)).fetchone()[0], "pending")
        with self.assertRaises(ValueError):
            bot.add_reminder(self.db, "customer@c.us", "2030-01-01T11:00:00", "Call")
        event = {**self.event, "data": {**self.event["data"], "id": "msg2"}}
        bot.accept(self.db, event)
        self.assertEqual(self.db.execute("SELECT state FROM reminders").fetchone()[0], "cancelled")
        self.assertEqual(self.db.execute("SELECT state FROM drafts").fetchone()[0], "superseded")

    def test_due_reminder_notifies_only_owner_once(self):
        with self.db:
            self.db.execute("INSERT INTO reminders(chat,due,note) VALUES(?,?,?)", ("customer@c.us", 0, "Follow up"))
        with patch.object(bot, "send_text", return_value="notice") as send:
            bot.tick(self.db)
            bot.tick(self.db)
            send.assert_called_once_with("owner@c.us", "Follow up: customer@c.us\nFollow up")

    def test_model_failure_preserves_queue(self):
        bot.accept(self.db, self.event)
        with patch.object(bot, "generate", side_effect=RuntimeError("offline")), self.assertLogs(bot.LOG, level="ERROR"):
            bot.process_one(self.db)
        row = self.db.execute("SELECT * FROM inbox").fetchone()
        self.assertEqual(row["state"], "pending")
        self.assertEqual(row["attempts"], 1)

    def test_signed_webhook_and_tampering(self):
        with TestClient(create_app(run_worker=False)) as client:
            url = "/openwa/webhook"
            raw = json.dumps(self.event).encode()
            signature = "sha256=" + hmac.new(b"a-long-test-secret", raw, hashlib.sha256).hexdigest()
            self.assertEqual(client.post(url, content=raw, headers={"X-OpenWA-Signature": "bad"}).status_code, 401)
            self.assertEqual(self.db.execute("SELECT count(*) FROM inbox").fetchone()[0], 0)
            for _ in range(2):
                self.assertEqual(client.post(url, content=raw, headers={"X-OpenWA-Signature": signature}).status_code, 200)
            self.assertEqual(self.db.execute("SELECT count(*) FROM inbox").fetchone()[0], 1)



if __name__ == "__main__":
    unittest.main()
