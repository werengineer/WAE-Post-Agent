import hashlib
import hmac
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.api.main import create_app
from app.services import cloudapi
from app.tools import whatsapp as bot

CUSTOMER = "919876543210@c.us"
OWNER = "919000000001@c.us"


def message_body(phone_id="111", sender="919876543210", text="Need 10 purifiers", message_id="wamid.1", kind="text"):
    message = {"from": sender, "id": message_id, "type": kind}
    if kind == "text":
        message["text"] = {"body": text}
    return {"object": "whatsapp_business_account", "entry": [{"id": "waba", "changes": [{"field": "messages", "value": {
        "messaging_product": "whatsapp", "metadata": {"phone_number_id": phone_id, "display_phone_number": "15550000000"},
        "contacts": [{"wa_id": sender}], "messages": [message]}}]}]}


def sign(raw, secret="app-secret"):
    return "sha256=" + hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()


class Response:
    def __init__(self, status, body):
        self.status_code, self._body = status, body

    def json(self):
        return self._body


class CloudApiTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {
            "WHATSAPP_PROVIDER": "cloud", "WHATSAPP_DB": str(Path(self.directory.name) / "test.sqlite3"),
            "WHATSAPP_PHONE_NUMBER_ID": "111", "WHATSAPP_ACCESS_TOKEN": "token", "WHATSAPP_APP_SECRET": "app-secret",
            "WHATSAPP_VERIFY_TOKEN": "a-long-verify-token", "OPENWA_OWNER_CHAT_ID": OWNER,
            "OPENWA_ALLOW_ALL_CHATS": "false", "OPENWA_TEST_CHAT_ID": CUSTOMER, "CLOUD_OWNER_TEMPLATE": "",
        })
        self.env.start()
        self.db = bot.connect()

    def tearDown(self):
        self.db.close()
        self.env.stop()
        self.directory.cleanup()

    # ---- parsing and signature
    def test_events_keep_only_text_messages_in_the_openwa_shape(self):
        events = cloudapi.events(message_body())
        self.assertEqual(events, [{"sessionId": "111", "event": "message.received", "data": {
            "id": "wamid.1", "chatId": CUSTOMER, "fromMe": False, "isGroup": False, "body": "Need 10 purifiers"}}])
        self.assertEqual(cloudapi.events(message_body(kind="image")), [])
        with self.assertRaises(ValueError):
            cloudapi.events({"object": "page"})
        statuses = {"object": "whatsapp_business_account", "entry": [{"changes": [{"field": "messages", "value": {"statuses": [{"id": "x"}]}}]}]}
        self.assertEqual(cloudapi.events(statuses), [])

    def test_signature_needs_the_exact_body_and_the_secret(self):
        raw = b'{"a":1}'
        self.assertTrue(cloudapi.verify_signature(raw, sign(raw)))
        self.assertFalse(cloudapi.verify_signature(raw + b" ", sign(raw)))
        self.assertFalse(cloudapi.verify_signature(raw, ""))
        with patch.dict(os.environ, {"WHATSAPP_APP_SECRET": ""}):
            self.assertFalse(cloudapi.verify_signature(raw, sign(raw, "")))

    # ---- webhook
    def test_url_verification(self):
        with TestClient(create_app(run_worker=False)) as client:
            ok = client.get("/whatsapp/webhook", params={"hub.mode": "subscribe", "hub.verify_token": "a-long-verify-token", "hub.challenge": "12345"})
            self.assertEqual((ok.status_code, ok.text), (200, "12345"))
            bad = client.get("/whatsapp/webhook", params={"hub.mode": "subscribe", "hub.verify_token": "wrong", "hub.challenge": "12345"})
            self.assertEqual(bad.status_code, 403)

    def test_webhook_stores_only_signed_messages_to_our_number_once(self):
        with TestClient(create_app(run_worker=False)) as client:
            raw = json.dumps(message_body()).encode()
            self.assertEqual(client.post("/whatsapp/webhook", content=raw, headers={"X-Hub-Signature-256": "sha256=bad"}).status_code, 401)
            self.assertEqual(self.db.execute("SELECT count(*) FROM inbox").fetchone()[0], 0)
            for _ in range(2):  # Meta may deliver the same message twice
                self.assertEqual(client.post("/whatsapp/webhook", content=raw, headers={"X-Hub-Signature-256": sign(raw)}).status_code, 200)
            self.assertEqual(self.db.execute("SELECT count(*) FROM inbox").fetchone()[0], 1)
            # another number of the same Meta app: acknowledged, not stored
            other = json.dumps(message_body(phone_id="222", message_id="wamid.2")).encode()
            self.assertEqual(client.post("/whatsapp/webhook", content=other, headers={"X-Hub-Signature-256": sign(other)}).status_code, 200)
            # a chat outside the test chat: acknowledged, not stored
            stranger = json.dumps(message_body(sender="911111111111", message_id="wamid.3")).encode()
            self.assertEqual(client.post("/whatsapp/webhook", content=stranger, headers={"X-Hub-Signature-256": sign(stranger)}).status_code, 200)
            self.assertEqual(self.db.execute("SELECT count(*) FROM inbox").fetchone()[0], 1)

    def test_webhook_is_off_for_the_openwa_provider(self):
        with patch.dict(os.environ, {"WHATSAPP_PROVIDER": "openwa"}), TestClient(create_app(run_worker=False)) as client:
            raw = json.dumps(message_body()).encode()
            self.assertEqual(client.post("/whatsapp/webhook", content=raw, headers={"X-Hub-Signature-256": sign(raw)}).status_code, 404)

    # ---- sending
    def test_send_text_posts_to_the_graph_api_and_returns_the_message_id(self):
        with patch("app.services.cloudapi.requests.post", return_value=Response(200, {"messages": [{"id": "wamid.out"}]})) as post:
            self.assertEqual(cloudapi.send_text(CUSTOMER, "Hello"), "wamid.out")
        url, = post.call_args.args
        self.assertTrue(url.endswith("/111/messages"))
        self.assertEqual(post.call_args.kwargs["headers"], {"Authorization": "Bearer token"})
        self.assertEqual(post.call_args.kwargs["json"]["to"], "919876543210")
        self.assertEqual(post.call_args.kwargs["json"]["text"]["body"], "Hello")

    def test_send_text_refuses_groups_empty_and_too_long_text(self):
        with patch("app.services.cloudapi.requests.post") as post:
            with self.assertRaises(ValueError):
                cloudapi.send_text("12345-678@g.us", "Hello")
            with self.assertRaises(ValueError):
                cloudapi.send_text(CUSTOMER, "   ")
            with self.assertRaises(ValueError):
                cloudapi.send_text(CUSTOMER, "x" * 4097)
            post.assert_not_called()

    def test_refusal_raises_without_leaking_the_token(self):
        refused = Response(400, {"error": {"code": 131030, "message": "Recipient not in allowed list"}})
        with patch("app.services.cloudapi.requests.post", return_value=refused):
            with self.assertRaises(RuntimeError) as caught:
                cloudapi.send_text(CUSTOMER, "Hello")
        self.assertIn("131030", str(caught.exception))
        self.assertNotIn("token", str(caught.exception).lower().replace("error code", ""))

    def test_owner_notification_falls_back_to_a_template_outside_the_24h_window(self):
        window = Response(400, {"error": {"code": 131047, "message": "Re-engagement message"}})
        accepted = Response(200, {"messages": [{"id": "wamid.tpl"}]})
        with patch.dict(os.environ, {"CLOUD_OWNER_TEMPLATE": "owner_notice"}), \
                patch("app.services.cloudapi.requests.post", side_effect=[window, accepted]) as post:
            self.assertEqual(cloudapi.send_text(OWNER, "Lead\nDraft #1"), "wamid.tpl")
        template = post.call_args_list[1].kwargs["json"]
        self.assertEqual(template["type"], "template")
        self.assertEqual(template["template"]["name"], "owner_notice")
        self.assertEqual(template["template"]["components"][0]["parameters"][0]["text"], "Lead | Draft #1")

    def test_a_customer_reply_never_falls_back_to_a_template(self):
        window = Response(400, {"error": {"code": 131047, "message": "Re-engagement message"}})
        with patch.dict(os.environ, {"CLOUD_OWNER_TEMPLATE": "owner_notice"}), \
                patch("app.services.cloudapi.requests.post", return_value=window) as post:
            with self.assertRaises(RuntimeError):
                cloudapi.send_text(CUSTOMER, "Thanks for writing")
        self.assertEqual(post.call_count, 1)

    def test_approve_sends_through_the_cloud_provider(self):
        with patch("app.services.cloudapi.requests.post", return_value=Response(200, {"messages": [{"id": "wamid.sent"}]})):
            with self.db:
                self.db.execute("INSERT INTO drafts(event_id,chat,text) VALUES(?,?,?)", ("e1", CUSTOMER, "We deliver in Delhi."))
            bot.approve(self.db, 1)
        row = self.db.execute("SELECT state,message_id FROM drafts WHERE id=1").fetchone()
        self.assertEqual((row["state"], row["message_id"]), ("sent", "wamid.sent"))


if __name__ == "__main__":
    unittest.main()
