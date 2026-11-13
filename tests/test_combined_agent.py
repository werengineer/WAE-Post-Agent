import json
import os
import tempfile
import unittest
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from app.agent.core import build_agent
from app.agent.commands import operator_command
from app.storage.database import connect
from app.tools import social
from app.tools.registry import TOOLS, create_reminder, draft_social_post, read_conversation


class ScriptedModel:
    def __init__(self, replies):
        self.replies = iter(replies)

    def bind_tools(self, tools):
        self.tools = tools
        return self

    def invoke(self, messages):
        return next(self.replies)


class CombinedAgentTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {
            "WHATSAPP_DB": str(Path(self.directory.name) / "test.sqlite3"),
            "OPENWA_ALLOW_ALL_CHATS": "false", "OPENWA_TEST_CHAT_ID": "test@lid",
        })
        self.env.start()
        with closing(connect()) as db, db:
            db.execute("INSERT INTO leads VALUES(?,?,?)", ("test@lid", json.dumps({"quantity": "10"}), 1))
            db.execute("INSERT INTO leads VALUES(?,?,?)", ("other@lid", "{}", 1))

    def tearDown(self):
        self.env.stop()
        self.directory.cleanup()

    def test_agent_selects_lead_and_reminder_tools_without_sending(self):
        at = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        model = ScriptedModel([
            AIMessage(content="", tool_calls=[{"id": "a", "name": "list_leads", "args": {}}]),
            AIMessage(content="", tool_calls=[{"id": "b", "name": "create_reminder", "args": {
                "chat": "test@lid", "at": at, "note": "Follow up"}}]),
            AIMessage(content="Saved your reminder."),
        ])
        with patch("app.services.openwa.requests.post") as send:
            result = build_agent(model=model).invoke({"messages": [HumanMessage(content="Remind me about this lead")]})
            send.assert_not_called()
        outcomes = [json.loads(m.content) for m in result["messages"] if isinstance(m, ToolMessage)]
        self.assertEqual(len(outcomes[0]["result"]), 1)
        self.assertEqual(outcomes[1]["result"]["state"], "pending")
        with closing(connect()) as db:
            self.assertEqual(db.execute("SELECT count(*) FROM reminders").fetchone()[0], 1)

    def test_model_cannot_call_approval_or_publish(self):
        self.assertFalse({"approve", "publish", "send_text"} & {t.name for t in TOOLS})
        model = ScriptedModel([
            AIMessage(content="", tool_calls=[{"id": "x", "name": "approve", "args": {"draft_id": 1}}]),
            AIMessage(content="Approval is required through the UI."),
        ])
        with patch("app.tools.whatsapp.send_text") as send:
            result = build_agent(model=model).invoke({"messages": [HumanMessage(content="Send it")]})
            send.assert_not_called()
        output = next(m for m in result["messages"] if isinstance(m, ToolMessage))
        self.assertFalse(json.loads(output.content)["ok"])

    def test_tools_keep_single_chat_boundary(self):
        with self.assertRaises(ValueError):
            read_conversation.invoke({"chat": "other@lid"})
        with self.assertRaises(ValueError):
            create_reminder.invoke({"chat": "other@lid", "at": "2030-01-01T00:00:00+00:00", "note": "No"})

    def test_social_tool_preserves_draft_workflow(self):
        saved = {"text": "Company update", "output": "posts/example.json", "post_id": "example"}
        with patch.object(social, "build_social_workflow") as workflow:
            workflow.return_value.invoke.return_value = saved
            result = draft_social_post.invoke({"platform": "linkedin", "topic": "New service"})
        self.assertEqual(result, saved)
        self.assertEqual(workflow.return_value.invoke.call_args.args[0]["platform"], "linkedin")

    def test_explicit_send_approves_saved_draft_once_without_model(self):
        from app.agent.core import run
        with closing(connect()) as db, db:
            db.execute("INSERT INTO drafts(event_id,chat,text) VALUES(?,?,?)", ("test-send", "test@lid", "Reviewed text"))
        with patch("app.tools.whatsapp.send_text", return_value="message-1") as send, patch("app.agent.core.get_model") as model:
            result = run("please send draft #1")
            self.assertTrue(result["tool_results"][0]["content"]["ok"])
            self.assertEqual(result["tool_results"][0]["content"]["result"]["state"], "sent")
            self.assertFalse(run("send draft #1")["tool_results"][0]["content"]["ok"])
            send.assert_called_once_with("test@lid", "Reviewed text")
            model.assert_not_called()

    def test_ambiguous_negated_or_quoted_send_never_authorizes(self):
        with patch("app.tools.whatsapp.send_text") as send:
            result = operator_command("send it")
            self.assertIn("Which WhatsApp draft", result["reply"])
            for message in ("don't send draft #1", 'What does "send draft #1" mean?',
                            "send draft #1 and draft #2", "send draft #1 to another person"):
                self.assertIsNone(operator_command(message))
            send.assert_not_called()

    def test_operator_send_keeps_chat_restriction_and_uncertain_guard(self):
        with closing(connect()) as db, db:
            db.execute("INSERT INTO drafts(event_id,chat,text) VALUES(?,?,?)", ("outside", "other@lid", "No"))
            db.execute("INSERT INTO drafts(event_id,chat,text) VALUES(?,?,?)", ("inside", "test@lid", "Reviewed"))
        with patch("app.tools.whatsapp.send_text") as send:
            self.assertFalse(operator_command("send draft #1")["tool_results"][0]["content"]["ok"])
            send.assert_not_called()
        with patch("app.tools.whatsapp.send_text", side_effect=TimeoutError), self.assertLogs(level="ERROR"):
            result = operator_command("send draft #2")
        self.assertFalse(result["tool_results"][0]["content"]["ok"])
        with patch("app.tools.whatsapp.send_text") as send:
            self.assertFalse(operator_command("send draft #2")["tool_results"][0]["content"]["ok"])
            send.assert_not_called()
        with closing(connect()) as db:
            self.assertEqual(db.execute("SELECT state FROM drafts WHERE id=2").fetchone()[0], "uncertain")
