import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient
from app.api.main import create_app
from pathlib import Path
from unittest.mock import patch

import requests

from app.tools import whatsapp as bot


class APITests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {
            "WHATSAPP_DB": str(Path(self.directory.name) / "test.sqlite3"),
            "OPENWA_ALLOW_ALL_CHATS": "false", "OPENWA_TEST_CHAT_ID": "test@lid", "WHATSAPP_API_TOKEN": "test-api-token",
            "WHATSAPP_API_ORIGINS": "http://localhost:3000",
        })
        self.env.start()
        self.db = bot.connect()
        with self.db:
            for chat in ("test@lid", "private@lid"):
                self.db.execute("INSERT INTO leads VALUES(?,?,?)", (chat, json.dumps({"product": "purifier"}), 1))
                self.db.execute("INSERT INTO inbox(id,chat,body,created_at,state) VALUES(?,?,?,?,?)", (chat, chat, "Need a purifier", 1, "done"))
                self.db.execute("INSERT INTO drafts(event_id,chat,text) VALUES(?,?,?)", (chat, chat, "Where is your office?"))
        self.client = TestClient(create_app(run_worker=False))
        self.client.__enter__()
        self.base = ""
        self.headers = {"Authorization": "Bearer test-api-token"}

    def tearDown(self):
        self.client.__exit__(None, None, None)
        self.db.close()
        self.env.stop()
        self.directory.cleanup()

    def call(self, method, path, **kwargs):
        return self.client.request(method, self.base + path, headers=self.headers, **kwargs)

    def test_auth_cors_and_disabled_api(self):
        self.assertEqual(self.client.get(self.base + "/api/leads").status_code, 401)
        bad = self.client.get(self.base + "/api/leads", headers={**self.headers, "Origin": "https://untrusted.test"})
        self.assertEqual(bad.status_code, 403)
        good = self.client.get(self.base + "/api/leads", headers={**self.headers, "Origin": "http://localhost:3000"})
        self.assertEqual(good.headers["Access-Control-Allow-Origin"], "http://localhost:3000")
        preflight = self.client.options(self.base + "/api/leads", headers={"Origin": "http://localhost:3000"})
        self.assertEqual(preflight.status_code, 200)
        with patch.dict(os.environ, {"WHATSAPP_API_TOKEN": ""}):
            self.assertEqual(self.call("GET", "/api/leads").status_code, 503)

    def test_lists_are_scoped_and_details_are_objects(self):
        for resource in ("leads", "drafts"):
            response = self.call("GET", "/api/" + resource)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["total"], 1)
            self.assertEqual(response.json()["items"][0]["chat"], "test@lid")
        self.assertIsInstance(self.call("GET", "/api/leads").json()["items"][0]["details"], dict)
        self.assertEqual(self.call("GET", "/api/drafts/2").status_code, 404)
        self.assertEqual(self.call("GET", "/api/leads/private%40lid/messages").status_code, 404)
        self.assertEqual(self.call("GET", "/api/leads?limit=501").status_code, 400)
        with patch.dict(os.environ, {"OPENWA_ALLOW_ALL_CHATS": "false", "OPENWA_TEST_CHAT_ID": ""}):
            self.assertEqual(self.call("GET", "/api/leads").json()["items"], [])

    def test_edit_does_not_send_and_approval_sends_only_once(self):
        with patch.object(bot, "send_text", return_value="sent-message") as send:
            edited = self.call("PATCH", "/api/drafts/1", json={"text": "Reviewed reply"})
            self.assertEqual(edited.status_code, 200)
            send.assert_not_called()
            approved = self.call("POST", "/api/drafts/1/approve", json={})
            self.assertEqual(approved.status_code, 200)
            self.assertEqual(approved.json()["state"], "sent")
            self.assertEqual(self.call("POST", "/api/drafts/1/approve", json={}).status_code, 409)
            send.assert_called_once_with("test@lid", "Reviewed reply")
        history = self.call("GET", "/api/leads/test%40lid/messages").json()
        self.assertEqual(history["total"], 2)
        self.assertEqual(history["items"][0]["direction"], "outbound")
        self.assertFalse(history["manual_phone_replies_included"])

    def test_operator_can_send_draft_through_agent_endpoint(self):
        with patch.object(bot, "send_text", return_value="operator-message") as send:
            response = self.call("POST", "/api/agent/run", json={"message": "send draft #1"})
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.json()["tool_results"][0]["content"]["ok"])
            send.assert_called_once_with("test@lid", "Where is your office?")

    def test_unrestricted_mode_lists_and_reads_each_chat_and_allows_approval(self):
        with patch.dict(os.environ, {"OPENWA_ALLOW_ALL_CHATS": "true"}):
            self.assertEqual(self.call("GET", "/api/leads").json()["total"], 2)
            self.assertEqual(self.call("GET", "/api/drafts").json()["total"], 2)
            history = self.call("GET", "/api/leads/private%40lid/messages").json()
            self.assertEqual(history["items"][0]["id"], "private@lid")
            with patch.object(bot, "send_text", return_value="other-message") as send:
                response = self.call("POST", "/api/agent/run", json={"message": "send draft #2"})
                self.assertTrue(response.json()["tool_results"][0]["content"]["ok"])
                send.assert_called_once_with("private@lid", "Where is your office?")
        self.assertEqual(self.call("GET", "/api/leads").json()["total"], 1)

    def test_uncertain_approval_is_reported_without_retry(self):
        with patch.object(bot, "send_text", side_effect=requests.Timeout), self.assertLogs(level="ERROR"):
            response = self.call("POST", "/api/drafts/1/approve", json={})
        self.assertEqual(response.status_code, 502)
        self.assertEqual(self.call("GET", "/api/drafts/1").json()["state"], "uncertain")
        self.assertEqual(self.call("POST", "/api/drafts/1/approve", json={}).status_code, 409)

    def test_reject_reminders_and_validation(self):
        self.assertEqual(self.call("POST", "/api/drafts/1/reject", json={}).json()["state"], "rejected")
        self.assertEqual(self.call("POST", "/api/drafts/1/approve", json={}).status_code, 409)
        at = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        response = self.call("POST", "/api/reminders", json={"chat": "test@lid", "at": at, "note": "Follow up"})
        self.assertEqual(response.status_code, 201)
        reminder_id = response.json()["id"]
        self.assertEqual(self.call("GET", "/api/reminders?state=pending").json()["total"], 1)
        self.assertEqual(self.call("POST", f"/api/reminders/{reminder_id}/cancel", json={}).json()["state"], "cancelled")
        self.assertEqual(self.call("POST", f"/api/reminders/{reminder_id}/cancel", json={}).status_code, 409)
        self.assertEqual(self.call("POST", "/api/reminders", json={"chat": "private@lid", "at": at, "note": "No"}).status_code, 400)
        self.assertEqual(self.call("PATCH", "/api/drafts/1", json={"text": 123}).status_code, 400)
        self.assertEqual(self.call("POST", "/api/reminders", content="[").status_code, 400)
        self.assertEqual(self.call("POST", "/api/reminders", json=[]).status_code, 400)

    def test_status_does_not_expose_credentials(self):
        with patch("app.api.operations.requests.get", return_value=type("Response", (), {
            "raise_for_status": lambda s: None,
            "json": lambda s: [{"id": "session", "status": "ready", "secret": "hidden"}],
        })()), patch.dict(os.environ, {"OPENWA_BASE_URL": "http://localhost:2785", "OPENWA_API_KEY": "hidden", "OPENWA_SESSION_ID": "session"}):
            # Avoid patching the test client's requests.get as well.
            from app.api.operations import connection_status
            result = connection_status()
        self.assertEqual(result["session_status"], "ready")
        self.assertNotIn("hidden", json.dumps(result))

    def test_openapi_and_body_limits(self):
        schema = self.client.get("/openapi.json").json()
        self.assertIn("/api/drafts/{draft_id}/approve", schema["paths"])
        self.assertIn("ReplyEdit", schema["components"]["schemas"])
        self.assertIn("HTTPBearer", schema["components"]["securitySchemes"])
        self.assertEqual(self.client.get("/docs").status_code, 200)
        self.assertEqual(self.client.post("/api/reminders", headers=self.headers, content=b"x" * 65537).status_code, 413)
        self.assertEqual(self.client.post("/openwa/webhook", content=b"x" * 1048577).status_code, 413)

    def test_combined_agent_and_social_routes_are_authenticated(self):
        self.assertEqual(self.client.post("/api/agent/run", json={"message": "List my leads"}).status_code, 401)
        tools = self.call("GET", "/api/agent/tools").json()
        names = {item["name"] for item in tools["tools"]}
        self.assertIn("draft_social_post", names)
        self.assertIn("create_reminder", names)
        self.assertNotIn("publish", names)
        with patch("app.agent.core.run", return_value={"reply": "Done", "tool_calls": [], "tool_results": []}) as run:
            response = self.call("POST", "/api/agent/run", json={"message": "List leads"})
            self.assertEqual(response.status_code, 200)
            run.assert_called_once_with("List leads")
        self.assertEqual(self.call("POST", "/api/posts/not-a-uuid/publish").status_code, 400)
        with patch("app.tools.registry.draft_social_post") as draft_tool:
            draft_tool.invoke.return_value = {"text": "Company news", "post_id": "example"}
            response = self.call("POST", "/api/posts/draft", json={"platform": "linkedin", "topic": "Company news"})
            self.assertEqual(response.status_code, 201)

    def test_worker_lifespan_stops_cleanly(self):
        with patch("app.services.scheduler.tick"), patch.dict(os.environ, {
            "OPENWA_BASE_URL": "http://localhost:2785", "OPENWA_API_KEY": "fake",
            "OPENWA_SESSION_ID": "fake", "OPENWA_OWNER_CHAT_ID": "owner@c.us",
            "OPENWA_WEBHOOK_SECRET": "long-test-secret", "GROQ_API_KEY": "fake",
        }):
            app = create_app()
            with TestClient(app):
                thread = app.state.worker_thread
                self.assertTrue(thread.is_alive())
            self.assertFalse(thread.is_alive())


if __name__ == "__main__":
    unittest.main()
