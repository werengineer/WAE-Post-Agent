import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.agent import drafting
from app.services import style

ANDROID = """12/05/2026, 11:05 pm - Messages and calls are end-to-end encrypted. No one outside of this chat can read them.
12/05/2026, 11:05 pm - Rahul: Mujhe courses ke baare mein jaanna hai
12/05/2026, 11:06 pm - Rahul: kab shuru hoga?
12/05/2026, 11:08 pm - WAE Team: Namaste Rahul ji! 🙏
Aap kaunsa course dekh rahe ho?
12/05/2026, 11:09 pm - WAE Team: Hum aapko details bhej dete hain
12/05/2026, 11:10 pm - Rahul: <Media omitted>
12/05/2026, 11:11 pm - Rahul: Mera number +91 98765 43210 hai, mail rahul@example.com
12/05/2026, 11:12 pm - WAE Team: Ji sir, kal subah call karte hain. https://example.com/x
12/05/2026, 11:13 pm - WAE Team: This message was deleted
"""

IPHONE = """[12/05/26, 11:05:12 PM] Rahul: Hi, internship ke liye apply karna hai
[12/05/26, 11:06:40 PM] WAE Team: Hi Rahul! Please apni branch aur year bata dijiye.
"""


class ParseTests(unittest.TestCase):
    def test_android_export_joins_lines_and_drops_noise(self):
        messages = style.parse_export(ANDROID)
        self.assertEqual([m[0] for m in messages], ["Rahul", "Rahul", "WAE Team", "WAE Team", "Rahul", "WAE Team"])
        self.assertEqual(messages[2][1], "Namaste Rahul ji! 🙏\nAap kaunsa course dekh rahe ho?")
        self.assertNotIn("deleted", " ".join(m[1] for m in messages))
        self.assertNotIn("omitted", " ".join(m[1] for m in messages))

    def test_iphone_export(self):
        self.assertEqual(style.parse_export(IPHONE), [
            ("Rahul", "Hi, internship ke liye apply karna hai"),
            ("WAE Team", "Hi Rahul! Please apni branch aur year bata dijiye.")])

    def test_pairs_group_a_run_of_our_messages_into_one_reply(self):
        got = style.pairs(style.parse_export(ANDROID), "wae")
        self.assertEqual(len(got), 2)
        self.assertEqual(got[0][0], "Mujhe courses ke baare mein jaanna hai\nkab shuru hoga?")
        self.assertTrue(got[0][1].endswith("Hum aapko details bhej dete hain"))
        self.assertIn("kal subah call", got[1][1])

    def test_mask_hides_numbers_emails_and_links(self):
        text = style.mask("Call +91 98765 43210 or rahul@example.com, see https://example.com/x")
        self.assertEqual(text, "Call <number> or <email>, see <link>")
        self.assertEqual(style.mask("2 din baad, 6 baje"), "2 din baad, 6 baje")

    def test_examples_are_masked_and_limited(self):
        pair_list = [(f"customer asks {i}", f"Namaste ji, yeh hamara reply number {i}") for i in range(40)]
        examples = style.pick_examples(pair_list, 5)
        self.assertEqual(len(examples), 5)
        self.assertEqual(len({e["reply"] for e in examples}), 5)
        short = style.pick_examples([("hi", "ok")], 5)  # a one-word reply says nothing about style
        self.assertEqual(short, [])


class LearnAndUseTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.path = Path(self.directory.name) / "style.json"
        self.env = patch.dict(os.environ, {"STYLE_FILE": str(self.path)})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.directory.cleanup()

    def test_learn_saves_guide_and_examples_and_load_reads_them(self):
        result = style.learn([ANDROID, IPHONE], "WAE Team", model=object(), summarize=lambda model, texts: f"short Hinglish, {len(texts)} msgs")
        self.assertEqual(result["learned_from_messages"], 4)  # 3 in the Android export (the deleted one does not count) + 1 in the iPhone export
        saved = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertTrue(saved["guide"].startswith("short Hinglish"))
        self.assertNotIn("98765", json.dumps(saved))
        self.assertNotIn("rahul@example.com", json.dumps(saved))
        loaded = style.load()
        self.assertEqual(loaded["guide"], saved["guide"])
        self.assertGreaterEqual(len(loaded["examples"]), 1)

    def test_learn_with_a_wrong_name_lists_the_names_in_the_export(self):
        with self.assertRaises(ValueError) as error:
            style.learn([ANDROID], "Nobody", model=object(), summarize=lambda m, t: "x")
        self.assertIn("WAE Team", str(error.exception))
        self.assertFalse(self.path.exists())

    def test_without_a_file_nothing_changes(self):
        self.assertIsNone(style.load())
        payload = {"a": 1}
        self.assertEqual(style.apply(payload), ("", payload))

    def test_a_broken_file_is_ignored(self):
        self.path.write_text("{not json", encoding="utf-8")
        self.assertIsNone(style.load())
        self.path.write_text(json.dumps({"guide": "  "}), encoding="utf-8")
        self.assertIsNone(style.load())

    def test_the_reply_prompt_gets_the_style_only_when_it_exists(self):
        db = MagicMock()
        db.execute.return_value = []
        db.execute.return_value = MagicMock(fetchone=lambda: None, __iter__=lambda self: iter([]))
        model = MagicMock()
        calls = []
        model.with_structured_output.return_value.invoke.side_effect = lambda messages: calls.append(messages) or MagicMock()
        with patch.object(drafting, "get_model", return_value=model):
            drafting.generate(db, "919876543210@c.us")
            self.path.write_text(json.dumps({"guide": "Short Hinglish, warm, ji/sir", "examples": [{"customer": "fees?", "reply": "Ji, team details share karegi 🙏"}]}), encoding="utf-8")
            drafting.generate(db, "919876543210@c.us")
        plain_system, plain_human = calls[0][0][1], json.loads(calls[0][1][1])
        styled_system, styled_human = calls[1][0][1], json.loads(calls[1][1][1])
        self.assertNotIn("style_guide", plain_human)
        self.assertNotIn("style_examples", plain_human)
        self.assertNotIn("style_guide", plain_system)
        self.assertEqual(styled_human["style_guide"], "Short Hinglish, warm, ji/sir")
        self.assertEqual(styled_human["style_examples"][0]["reply"], "Ji, team details share karegi 🙏")
        self.assertIn("brand_rule and never_state", styled_system)  # the facts rules stay above the style
        self.assertIn("company", styled_human)


if __name__ == "__main__":
    unittest.main()
