import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from app.services import followups
from app.tools import whatsapp as bot

CUSTOMER = "919876543210@c.us"


class FollowUpTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {
            "WHATSAPP_DB": str(Path(self.directory.name) / "test.sqlite3"), "WHATSAPP_PROVIDER": "openwa",
            "OPENWA_SESSION_ID": "session", "OPENWA_OWNER_CHAT_ID": "owner@c.us",
            "OPENWA_ALLOW_ALL_CHATS": "false", "OPENWA_TEST_CHAT_ID": CUSTOMER,
            "FOLLOWUP": "on", "FOLLOWUP_DELAYS_HOURS": "24", "FOLLOWUP_HOURS": "0-24", "FOLLOWUP_MAX_PER_DAY": "200",
            "AUTO_REPLY": "off",
        })
        self.env.start()
        self.db = bot.connect()
        self.counter = 0

    def tearDown(self):
        self.db.close()
        self.env.stop()
        self.directory.cleanup()

    # ---- helpers
    def reply_sent(self, chat=CUSTOMER):
        """A reply to the customer goes out (the way an approval or an automatic reply sends it): this is what plans the follow-up."""
        self.counter += 1
        with self.db:
            draft_id = self.db.execute("INSERT INTO drafts(event_id,chat,text) VALUES(?,?,?)", (f"e{self.counter}", chat, "Thanks, which city?")).lastrowid
        with patch.object(bot, "send_text", return_value="wa-reply"):
            bot.approve(self.db, draft_id)
        return draft_id

    def customer_writes(self, text, chat=CUSTOMER):
        self.counter += 1
        event = {"sessionId": "session", "event": "message.received", "data": {
            "id": f"m{self.counter}", "chatId": chat, "body": text, "fromMe": False, "isGroup": False}}
        self.assertTrue(bot.accept(self.db, event))

    def rows(self):
        return [dict(r) for r in self.db.execute("SELECT * FROM followups ORDER BY id")]

    def make_due(self):
        with self.db:
            self.db.execute("UPDATE followups SET due=? WHERE state='pending'", (time.time() - 1,))

    def run_tick(self, text="Just checking in: are you still interested?", send=None):
        with patch("app.agent.drafting.generate_followup", return_value=text), \
                patch.object(followups, "send_text", **(send or {"return_value": "wa-follow"})) as sender:
            followups.tick(self.db)
        return sender

    # ---- planning
    def test_nothing_is_planned_when_switched_off(self):
        with patch.dict(os.environ, {"FOLLOWUP": "off"}):
            self.reply_sent()
        self.assertEqual(self.rows(), [])

    def test_a_reply_plans_one_follow_up_24_hours_later(self):
        before = time.time()
        self.reply_sent()
        self.reply_sent()  # a second reply while one is waiting does not stack another
        rows = self.rows()
        self.assertEqual(len(rows), 1)
        self.assertEqual((rows[0]["chat"], rows[0]["step"], rows[0]["state"]), (CUSTOMER, 1, "pending"))
        self.assertAlmostEqual(rows[0]["due"], before + 24 * 3600, delta=10)

    def test_groups_and_the_cloud_provider_get_none(self):
        self.assertFalse(followups.schedule(self.db, "120363000000000000@g.us"))
        with patch.dict(os.environ, {"WHATSAPP_PROVIDER": "cloud"}):
            self.assertFalse(followups.enabled())
            self.assertFalse(followups.schedule(self.db, CUSTOMER))
        self.assertEqual(self.rows(), [])

    # ---- the customer answers or says stop
    def test_a_new_message_from_the_customer_cancels_the_waiting_follow_up(self):
        self.reply_sent()
        self.customer_writes("Delhi mein chahiye")
        self.assertEqual(self.rows()[0]["state"], "cancelled")
        sender = self.run_tick()
        sender.assert_not_called()

    def test_stop_in_english_or_hinglish_blocks_every_future_follow_up(self):
        for index, text in enumerate(["please stop messaging me", "mujhe nahi chahiye", "not interested, thanks"]):
            chat = f"91900000000{index}@c.us"
            with patch.dict(os.environ, {"OPENWA_ALLOW_ALL_CHATS": "true"}):
                self.reply_sent(chat)
                self.customer_writes(text, chat)
                self.assertTrue(followups.is_opted_out(self.db, chat), text)
                self.assertFalse(followups.schedule(self.db, chat))
                self.reply_sent(chat)  # even a later reply plans nothing
        self.assertEqual({r["state"] for r in self.rows()}, {"cancelled"})

    def test_an_ordinary_message_is_not_a_stop(self):
        self.reply_sent()
        self.customer_writes("I want to know the price, please")
        self.assertFalse(followups.is_opted_out(self.db, CUSTOMER))

    # ---- sending
    def test_a_due_follow_up_is_sent_once_and_the_owner_is_told(self):
        self.reply_sent()
        self.make_due()
        sender = self.run_tick()
        sender.assert_called_once_with(CUSTOMER, "Just checking in: are you still interested?")
        row = self.rows()[0]
        self.assertEqual((row["state"], row["message_id"]), ("sent", "wa-follow"))
        self.assertIsNotNone(row["sent_at"])
        notice = self.db.execute("SELECT text, chat FROM notices ORDER BY id DESC LIMIT 1").fetchone()
        self.assertIn("Follow-up #1 sent", notice["text"])
        self.assertEqual(notice["chat"], CUSTOMER)
        self.run_tick().assert_not_called()  # nothing is left to send

    def test_it_waits_until_it_is_due(self):
        self.reply_sent()
        self.run_tick().assert_not_called()
        self.assertEqual(self.rows()[0]["state"], "pending")

    def test_a_second_step_follows_the_first_when_configured(self):
        with patch.dict(os.environ, {"FOLLOWUP_DELAYS_HOURS": "24,72"}):
            self.reply_sent()
            self.make_due()
            self.run_tick()
            rows = self.rows()
            self.assertEqual([(r["step"], r["state"]) for r in rows], [(1, "sent"), (2, "pending")])
            self.assertAlmostEqual(rows[1]["due"], rows[0]["sent_at"] + 72 * 3600, delta=10)
            self.make_due()
            self.run_tick()
            self.assertEqual([(r["step"], r["state"]) for r in self.rows()], [(1, "sent"), (2, "sent")])  # no third step

    def test_it_waits_for_the_working_hours(self):
        self.reply_sent()
        self.make_due()
        with patch.object(followups, "in_hours", return_value=False):
            sender = self.run_tick()
        sender.assert_not_called()
        self.assertEqual(self.rows()[0]["state"], "pending")  # still waiting for the morning

    def test_working_hours_window(self):
        from datetime import datetime
        from zoneinfo import ZoneInfo
        zone = ZoneInfo("Asia/Kolkata")
        with patch.dict(os.environ, {"FOLLOWUP_HOURS": "10-19"}):
            self.assertTrue(followups.in_hours(datetime(2026, 11, 14, 10, 0, tzinfo=zone)))
            self.assertTrue(followups.in_hours(datetime(2026, 11, 14, 18, 59, tzinfo=zone)))
            self.assertFalse(followups.in_hours(datetime(2026, 11, 14, 19, 0, tzinfo=zone)))
            self.assertFalse(followups.in_hours(datetime(2026, 11, 14, 3, 0, tzinfo=zone)))

    def test_the_daily_limit_holds_the_rest_back(self):
        with self.db:
            self.db.execute("INSERT INTO followups(chat,step,due,state,sent_at,created_at) VALUES(?,?,?,?,?,?)",
                            ("911111111111@c.us", 1, 0, "sent", time.time() - 60, time.time() - 90000))
        self.reply_sent()
        self.make_due()
        with patch.dict(os.environ, {"FOLLOWUP_MAX_PER_DAY": "1"}):
            sender = self.run_tick()
        sender.assert_not_called()
        self.assertEqual(self.rows()[-1]["state"], "pending")

    def test_a_failed_send_is_uncertain_and_never_repeated(self):
        self.reply_sent()
        self.make_due()
        with self.assertLogs(followups.LOG, level="ERROR"):
            sender = self.run_tick(send={"side_effect": TimeoutError})
        self.assertEqual(sender.call_count, 1)
        self.assertEqual(self.rows()[0]["state"], "uncertain")
        self.assertIn("uncertain", self.db.execute("SELECT text FROM notices ORDER BY id DESC LIMIT 1").fetchone()[0])
        self.run_tick().assert_not_called()

    def test_text_that_cannot_be_written_is_retried_later_and_then_given_up(self):
        self.reply_sent()
        for attempt in range(1, followups.MAX_ATTEMPTS + 1):
            self.make_due()
            with patch("app.agent.drafting.generate_followup", side_effect=RuntimeError("offline")), \
                    patch.object(followups, "send_text") as sender, self.assertLogs(followups.LOG, level="ERROR"):
                followups.tick(self.db)
            sender.assert_not_called()
            row = self.rows()[0]
            self.assertEqual(row["attempts"], attempt)
            self.assertEqual(row["state"], "failed" if attempt == followups.MAX_ATTEMPTS else "pending")

    def test_nothing_is_sent_when_the_model_has_nothing_to_say(self):
        self.reply_sent()
        self.make_due()
        sender = self.run_tick(text="  ")
        sender.assert_not_called()
        self.assertEqual(self.rows()[0]["state"], "cancelled")

    def test_a_chat_outside_the_allowed_chats_is_dropped(self):
        self.reply_sent()
        self.make_due()
        with patch.dict(os.environ, {"OPENWA_TEST_CHAT_ID": "919000000009@c.us"}):
            sender = self.run_tick()
        sender.assert_not_called()
        self.assertEqual(self.rows()[0]["state"], "cancelled")

    # ---- a time the customer asked for ("abhi free nahi hu, shaam ko baat karte hain")
    def test_requested_time_reading(self):
        from datetime import datetime, timedelta
        from zoneinfo import ZoneInfo
        now = datetime.now(ZoneInfo("Asia/Kolkata"))
        in_three_hours = now + timedelta(hours=3)
        stamp = followups.requested_time(in_three_hours.isoformat())
        self.assertAlmostEqual(stamp, in_three_hours.timestamp(), delta=2)
        # a time without an offset is read in AGENT_TIMEZONE
        self.assertAlmostEqual(followups.requested_time(in_three_hours.replace(tzinfo=None).isoformat()), stamp, delta=2)
        for bad in ("", "  ", "kal shaam", "2020-01-01T10:00:00+05:30", (now + timedelta(days=31)).isoformat(),
                    (now + timedelta(seconds=10)).isoformat(), None):
            self.assertIsNone(followups.requested_time(bad), bad)

    def test_the_time_the_customer_asked_for_replaces_the_delay_and_the_owner_is_told(self):
        asked = time.time() + 3 * 3600
        self.assertTrue(followups.schedule(self.db, CUSTOMER, None, requested_at=asked))
        row = self.rows()[0]
        self.assertAlmostEqual(row["due"], asked, delta=2)
        self.assertEqual(row["requested"], 1)
        self.assertIn("asked us to get back", self.db.execute("SELECT text FROM notices").fetchone()[0])

    def test_a_requested_time_that_has_passed_falls_back_to_the_normal_delay(self):
        before = time.time()
        followups.schedule(self.db, CUSTOMER, None, requested_at=before - 3600)
        row = self.rows()[0]
        self.assertEqual(row["requested"], 0)
        self.assertAlmostEqual(row["due"], before + 24 * 3600, delta=10)

    def test_a_requested_follow_up_may_use_the_wider_window(self):
        from datetime import datetime
        from zoneinfo import ZoneInfo
        zone = ZoneInfo("Asia/Kolkata")
        with patch.dict(os.environ, {"FOLLOWUP_HOURS": "10-19", "FOLLOWUP_REQUESTED_HOURS": "8-21"}):
            evening = datetime(2026, 11, 14, 20, 0, tzinfo=zone)
            self.assertFalse(followups.in_hours(evening))
            self.assertTrue(followups.in_hours(evening, requested=True))
            self.assertFalse(followups.in_hours(datetime(2026, 11, 14, 22, 0, tzinfo=zone), requested=True))

    def test_the_requested_follow_up_is_sent_when_its_own_window_is_open(self):
        followups.schedule(self.db, CUSTOMER, None, requested_at=time.time() + 3600)
        self.make_due()
        with patch.object(followups, "in_hours", side_effect=lambda now=None, requested=False: requested):
            sender = self.run_tick()
        sender.assert_called_once()
        self.assertEqual(self.rows()[0]["state"], "sent")

    def test_the_follow_up_text_is_told_that_the_customer_asked_for_this_time(self):
        followups.schedule(self.db, CUSTOMER, None, requested_at=time.time() + 3600)
        self.make_due()
        with patch("app.agent.drafting.generate_followup", return_value="Aap ne kaha tha, ab free hain?") as writer, \
                patch.object(followups, "send_text", return_value="wa"):
            followups.tick(self.db)
        self.assertEqual(writer.call_args.args[3], True)  # (db, chat, step, requested)

    def test_a_time_the_customer_names_travels_from_the_model_through_the_reply_to_the_follow_up(self):
        from datetime import datetime, timedelta
        from zoneinfo import ZoneInfo
        from app.agent.drafting import LeadDraft
        asked = (datetime.now(ZoneInfo("Asia/Kolkata")) + timedelta(hours=3)).isoformat()
        self.customer_writes("Abhi free nahi hu, shaam ko baat karte hain")
        lead = LeadDraft(is_lead=True, details={}, reply="Theek hai, shaam ko baat karte hain.", follow_up_at=asked)
        with patch.object(bot, "generate", return_value=lead):
            bot.process_one(self.db)
        draft = self.db.execute("SELECT * FROM drafts").fetchone()
        self.assertAlmostEqual(draft["follow_up_at"], followups.requested_time(asked), delta=2)
        with patch.object(bot, "send_text", return_value="wa-reply"):
            bot.approve(self.db, draft["id"])
        row = self.rows()[0]
        self.assertEqual(row["requested"], 1)
        self.assertAlmostEqual(row["due"], draft["follow_up_at"], delta=2)


if __name__ == "__main__":
    unittest.main()
