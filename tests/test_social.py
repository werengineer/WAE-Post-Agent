import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from app.tools.social import build_social_workflow, publish, validate_text


class SocialWorkflowTests(unittest.TestCase):
    def test_graph_saves_generated_draft(self):
        with tempfile.TemporaryDirectory() as directory:
            output = str(Path(directory) / "post.json")
            def save_result(state):
                Path(output).write_text(json.dumps(state), encoding="utf-8")
                return {"output": output}
            with patch("app.tools.social.get_model") as model, patch("app.tools.social.save", side_effect=save_result):
                model.return_value.with_structured_output.return_value.invoke.return_value = Mock(text="Hello company!")
                result = build_social_workflow().invoke({"company": {"name": "Test"}, "topic": "Hello", "platform": "x"})
                self.assertEqual(json.loads(Path(output).read_text())["text"], "Hello company!")
                self.assertEqual(result["output"], output)

    def test_invalid_text(self):
        for text in ("", " " , "a" * 281):
            with self.assertRaises(ValueError):
                validate_text(text, "x")

    def test_submission_and_duplicate_guard(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "post.json"
            path.write_text(json.dumps({"post_id": "123", "platform": "x", "text": "Hello", "status": "draft"}))
            with patch.dict("os.environ", {"SOCIAL_WEBHOOK_URL": "https://example.com/post"}), patch("app.tools.social.requests.post", return_value=Mock(status_code=202)) as send:
                publish(path)
                self.assertEqual(send.call_args.kwargs["headers"]["Idempotency-Key"], "123")
                self.assertEqual(json.loads(path.read_text())["status"], "submitted")
                with self.assertRaises(ValueError):
                    publish(path)
                self.assertEqual(send.call_count, 1)

    def test_http_failure_preserves_draft(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "post.json"
            path.write_text(json.dumps({"post_id": "123", "platform": "x", "text": "Hello", "status": "draft"}))
            with patch.dict("os.environ", {"SOCIAL_WEBHOOK_URL": "https://example.com/post"}), patch("app.tools.social.requests.post", return_value=Mock(status_code=500)):
                with self.assertRaises(ValueError):
                    publish(path)
                self.assertEqual(json.loads(path.read_text())["status"], "draft")


if __name__ == "__main__":
    unittest.main()
