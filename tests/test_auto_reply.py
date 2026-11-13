import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import requests

from app.agent.drafting import LeadDraft
from app.tools import whatsapp as bot

CUSTOMER = "919876543210@c.us"


class AutoReplyTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {
            "WHATSAPP_DB": str(Path(self.directory.name) / "test.sqlite3"), "WHATSAPP_PROVIDER": "openwa",
            "OPENWA_SESSION_ID": "session", "OPENWA_OWNER_CHAT_ID": "owner@c.us",
            "OPENWA_ALLOW_ALL_CHATS": "true", "OPENWA_TEST_CHAT_ID": "",
            "AUTO_REPLY": "on", "AUTO_REPLY_MAX_PER_CHAT_HOUR": "6", "AUTO_REPLY_MAX_PER_DAY": "1000",
        })
        self.env.start()
        self.db = bot.connect()
        self.lead = LeadDraft(is_lead=True, details={"need": "10 purifiers"}, reply="Yes, we can help. Which city?")

    def tearDown(self):
        self.db.close()
        self.env.stop()
        self.directory.cleanup()

    def receive(self, chat=CUSTOMER, message_id="m1", is_group=False):
        event = {"sessionId": "session", "event": "message.received", "data": {
            "id": message_id, "chatId": chat, "body": "Need 10 purifiers", "fromMe": False, "isGroup": is_group}}
        self.assertTrue(bot.accept(self.db, event))

    def draft(self):
        return self.db.execute("SELECT * FROM drafts ORDER BY id DESC LIMIT 1").fetchone()

    def test_off_by_default_keeps_a_draft(self):
        self.receive()
        with patch.dict(os.environ, {"AUTO_REPLY": "off"}), patch.object(bot, "generate", return_value=self.lead), patch.object(bot, "send_text") as send:
            bot.process_one(self.db)
        send.assert_not_called()
        self.assertEqual(self.draft()["state"], "draft")

    def test_on_sends_the_reply_once_and_tells_the_owner(self):
        self.receive()
        with patch.object(bot, "generate", return_value=self.lead), patch.object(bot, "send_text", return_value="wa-1") as send:
            bot.process_one(self.db)
            bot.process_one(self.db)  # nothing left to process: no second send
        send.assert_called_once_with(CUSTOMER, "Yes, we can help. Which city?")
        draft = self.draft()
        self.assertEqual((draft["state"], draft["message_id"]), ("sent", "wa-1"))
        self.assertEqual(self.db.execute("SELECT state FROM inbox").fetchone()[0], "done")
        self.assertIn("automatically", self.db.execute("SELECT text FROM notices ORDER BY id DESC LIMIT 1").fetchone()[0])

    def test_failed_send_is_uncertain_not_retried_and_does_not_rerun_the_model(self):
        self.receive()
        with patch.object(bot, "generate", return_value=self.lead) as model, patch.object(bot, "send_text", side_effect=requests.Timeout) as send, \
                self.assertLogs(bot.LOG, level="ERROR"):
            bot.process_one(self.db)
            bot.process_one(self.db)
        self.assertEqual(model.call_count, 1)
        self.assertEqual(send.call_count, 1)
        self.assertEqual(self.draft()["state"], "uncertain")
        self.assertEqual(self.db.execute("SELECT state FROM inbox").fetchone()[0], "done")
        self.assertIn("failed", self.db.execute("SELECT text FROM notices ORDER BY id DESC LIMIT 1").fetchone()[0])

    def test_per_chat_hourly_cap_leaves_a_draft(self):
        with self.db:
            for i in range(6):
                self.db.execute("INSERT INTO drafts(event_id,chat,text,state,sent_at) VALUES(?,?,?,?,?)",
                                (f"old{i}", CUSTOMER, "earlier reply", "sent", time.time() - 60))
        self.receive(message_id="m-cap")
        with patch.object(bot, "generate", return_value=self.lead), patch.object(bot, "send_text") as send:
            bot.process_one(self.db)
        send.assert_not_called()
        self.assertEqual(self.draft()["state"], "draft")
        self.assertIn("Review with", self.db.execute("SELECT text FROM notices ORDER BY id DESC LIMIT 1").fetchone()[0])

    def test_daily_cap_leaves_a_draft(self):
        with patch.dict(os.environ, {"AUTO_REPLY_MAX_PER_DAY": "1"}):
            with self.db:
                self.db.execute("INSERT INTO drafts(event_id,chat,text,state,sent_at) VALUES(?,?,?,?,?)",
                                ("old", "911111111111@c.us", "earlier reply", "sent", time.time() - 60))
            self.receive(message_id="m-day")
            with patch.object(bot, "generate", return_value=self.lead), patch.object(bot, "send_text") as send:
                bot.process_one(self.db)
        send.assert_not_called()
        self.assertEqual(self.draft()["state"], "draft")

    def test_groups_always_wait_for_a_person(self):
        group = "120363000000000000@g.us"
        self.receive(chat=group, message_id="g1", is_group=True)
        with patch.object(bot, "generate", return_value=self.lead), patch.object(bot, "send_text") as send:
            bot.process_one(self.db)
        send.assert_not_called()
        self.assertEqual(self.draft()["state"], "draft")

    def test_messages_that_are_not_leads_get_no_reply(self):
        self.receive()
        spam = LeadDraft(is_lead=False, details={}, reply="")
        with patch.object(bot, "generate", return_value=spam), patch.object(bot, "send_text") as send:
            bot.process_one(self.db)
        send.assert_not_called()
        self.assertIsNone(self.draft())

    def test_other_chats_stay_blocked_when_not_all_chats_are_open(self):
        with patch.dict(os.environ, {"OPENWA_ALLOW_ALL_CHATS": "false", "OPENWA_TEST_CHAT_ID": "919000000009@c.us"}):
            event = {"sessionId": "session", "event": "message.received", "data": {
                "id": "x1", "chatId": CUSTOMER, "body": "Hi", "fromMe": False, "isGroup": False}}
            self.assertFalse(bot.accept(self.db, event))


if __name__ == "__main__":
    unittest.main()
