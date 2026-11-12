import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from agent import publish_direct
from social import PublishError, get_adapter

ENV = {"LINKEDIN_ACCESS_TOKEN": "t", "LINKEDIN_AUTHOR_URN": "urn:li:organization:1",
       "X_ACCESS_TOKEN": "t", "FACEBOOK_PAGE_ID": "9", "FACEBOOK_PAGE_TOKEN": "t",
       "INSTAGRAM_USER_ID": "7", "INSTAGRAM_ACCESS_TOKEN": "t"}


class SocialTests(unittest.TestCase):
    def setUp(self):
        p = patch.dict("os.environ", ENV)
        p.start()
        self.addCleanup(p.stop)

    def test_linkedin_escapes_and_keeps_hashtags(self):
        call = get_adapter("linkedin").plan({"text": "Hi (all) #WAE"})[0]
        self.assertEqual(call.json["commentary"], "Hi \\(all\\) #WAE")
        self.assertEqual(call.json["author"], "urn:li:organization:1")

    def test_x_and_facebook(self):
        with patch("social.adapters.requests.post", return_value=Mock(status_code=201, json=lambda: {"data": {"id": "5"}})):
            self.assertEqual(get_adapter("x").publish({"text": "hi"}), "5")
        with patch("social.adapters.requests.post", return_value=Mock(status_code=200, json=lambda: {"id": "9_1"})):
            self.assertEqual(get_adapter("facebook").publish({"text": "hi"}), "9_1")

    def test_instagram_two_steps_and_needs_image(self):
        with self.assertRaises(PublishError):
            get_adapter("instagram").plan({"text": "hi"})
        responses = [Mock(status_code=200, json=lambda: {"id": "c1"}), Mock(status_code=200, json=lambda: {"id": "m1"})]
        with patch("social.adapters.requests.post", side_effect=responses) as send:
            out = get_adapter("instagram").publish({"text": "hi", "image_url": "https://x.example/a.jpg"})
        self.assertEqual(out, "m1")
        self.assertEqual(send.call_args.kwargs["data"], {"creation_id": "c1"})

    def test_missing_credentials(self):
        with patch.dict("os.environ", {}, clear=True), self.assertRaises(PublishError):
            get_adapter("x").plan({"text": "hi"})

    def test_http_error(self):
        with patch("social.adapters.requests.post", return_value=Mock(status_code=403, text="no")), \
                self.assertRaises(PublishError):
            get_adapter("x").publish({"text": "hi"})

    def test_dry_run_sends_nothing_and_live_marks_published(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "p.json"
            path.write_text(json.dumps({"post_id": "1", "platform": "x", "text": "hi", "status": "draft"}))
            with patch("social.adapters.requests.post") as send:
                publish_direct(path)
                send.assert_not_called()
            with patch("social.adapters.requests.post", return_value=Mock(status_code=201, json=lambda: {"data": {"id": "5"}})):
                publish_direct(path, live=True)
            self.assertEqual(json.loads(path.read_text())["status"], "published")
            with self.assertRaises(ValueError):
                publish_direct(path, live=True)


if __name__ == "__main__":
    unittest.main()
