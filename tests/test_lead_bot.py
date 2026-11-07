import hashlib
import hmac
import unittest

from lead_bot import manager, store, whatsapp


class LeadBotTests(unittest.TestCase):
    def setUp(self):
        self.db = store.connect(":memory:")

    def test_classify(self):
        self.assertEqual(manager.classify("What is the price?"), "interested")
        self.assertEqual(manager.classify("STOP"), "opted_out")
        self.assertEqual(manager.classify("not interested"), "not_interested")
        self.assertEqual(manager.classify("ok"), "replied")

    def test_inbound_updates_status_followup_and_queues_reply(self):
        r = manager.handle_inbound(self.db, "+91 98765 43210", "Asha Rao", "pricing please", "w1")
        self.assertEqual(r["status"], "interested")
        self.assertIn("Asha", self.db.execute("SELECT body FROM outbox").fetchone()[0])
        self.assertEqual(self.db.execute("SELECT status FROM outbox").fetchone()[0], "pending_approval")
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM followups WHERE done=0").fetchone()[0], 1)

    def test_duplicate_webhook_ignored(self):
        manager.handle_inbound(self.db, "911", "", "hi", "w1")
        self.assertTrue(manager.handle_inbound(self.db, "911", "", "hi", "w1")["duplicate"])
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM messages").fetchone()[0], 1)

    def test_opt_out_cancels_everything(self):
        manager.handle_inbound(self.db, "911", "", "price?", "w1")
        manager.handle_inbound(self.db, "911", "", "stop", "w2")
        self.assertEqual(self.db.execute("SELECT opted_out FROM leads").fetchone()[0], 1)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM outbox WHERE status='pending_approval'").fetchone()[0], 0)
        self.assertIsNone(manager.due_reminders(self.db))

    def test_reminder_and_digest(self):
        manager.handle_inbound(self.db, "911", "Asha", "price?", "w1")
        self.db.execute("UPDATE followups SET due_at='2000-01-01'")
        self.assertIn("Asha", manager.due_reminders(self.db, mark=True))
        self.assertIn("interested 1", manager.digest(self.db))

    def test_signature_and_parse(self):
        body = b'{"a":1}'
        sig = "sha256=" + hmac.new(b"s", body, hashlib.sha256).hexdigest()
        self.assertTrue(whatsapp.verify_signature(body, sig, "s"))
        self.assertFalse(whatsapp.verify_signature(body, sig, ""))
        payload = {"entry": [{"changes": [{"value": {"contacts": [{"wa_id": "9", "profile": {"name": "A"}}],
                   "messages": [{"id": "m", "from": "9", "type": "text", "text": {"body": "hi"}}]}}]}]}
        self.assertEqual(whatsapp.parse_inbound(payload)[0]["text"], "hi")

    def test_send_disabled_by_default(self):
        with self.assertRaises(RuntimeError):
            whatsapp.send_text("9", "x")


if __name__ == "__main__":
    unittest.main()
