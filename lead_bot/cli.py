"""Command line + webhook server for the WhatsApp lead automation.

  python -m lead_bot.cli serve [--port 8080]      receive WhatsApp webhooks
  python -m lead_bot.cli add-lead PHONE [--name N]
  python -m lead_bot.cli remind                   queue reminder for Lokesh (outbox)
  python -m lead_bot.cli digest                   queue manager digest for the report chat
  python -m lead_bot.cli outbox | approve ID | send
"""

import argparse
import json
import os
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

from dotenv import load_dotenv

from . import manager, store, whatsapp


def make_handler(db_path: str):
    class Handler(BaseHTTPRequestHandler):
        def _reply(self, code, body=b""):
            self.send_response(code)
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            q = {k: v[0] for k, v in parse_qs(urlparse(self.path).query).items()}
            ch = whatsapp.verify_challenge(q, os.getenv("WHATSAPP_VERIFY_TOKEN", ""))
            self._reply(200, ch.encode()) if ch is not None else self._reply(403)

        def do_POST(self):
            raw = self.rfile.read(min(int(self.headers.get("Content-Length", 0)), 1_000_000))
            if not whatsapp.verify_signature(raw, self.headers.get("X-Hub-Signature-256", ""),
                                             os.getenv("WHATSAPP_APP_SECRET", "")):
                return self._reply(403)
            try:
                msgs = whatsapp.parse_inbound(json.loads(raw))
            except ValueError:
                return self._reply(400)
            db = store.connect(db_path)   # new connection per request (thread-safe)
            for m in msgs:
                manager.handle_inbound(db, m["phone"], m["name"], m["text"], m["wa_id"])
            db.close()
            self._reply(200)
    return Handler


def main() -> None:
    load_dotenv()
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    p.add_argument("--db", default=os.getenv("LEADS_DB", "leads.db"))
    c = p.add_subparsers(dest="cmd", required=True)
    s = c.add_parser("serve"); s.add_argument("--port", type=int, default=8080)
    a = c.add_parser("add-lead"); a.add_argument("phone"); a.add_argument("--name", default="")
    c.add_parser("remind"); c.add_parser("digest"); c.add_parser("outbox"); c.add_parser("send")
    ap = c.add_parser("approve"); ap.add_argument("id", type=int)
    args = p.parse_args()
    if args.cmd == "serve":
        HTTPServer(("0.0.0.0", args.port), make_handler(args.db)).serve_forever()
    db = store.connect(args.db)
    if args.cmd == "add-lead":
        lead = store.get_or_create_lead(db, args.phone, args.name)
        print(f"Lead {lead['id']} ready (status {lead['status']})")
    elif args.cmd in ("remind", "digest"):
        text = manager.due_reminders(db, mark=True) if args.cmd == "remind" else manager.digest(db)
        if not text:
            return print("Nothing due.")
        target = os.getenv("LOKESH_WHATSAPP" if args.cmd == "remind" else "REPORT_CHAT_WHATSAPP", "")
        if not target:
            return print(text + "\n\n(Set the target number env var to queue it.)")
        print(f"Queued #{store.queue_outbound(db, None, args.cmd, target, text)} for approval")
    elif args.cmd == "outbox":
        for r in db.execute("SELECT * FROM outbox ORDER BY id DESC LIMIT 50"):
            print(f"#{r['id']} [{r['status']}] {r['kind']} -> +{r['recipient']}: {r['body'][:100]}")
    elif args.cmd == "approve":
        db.execute("UPDATE outbox SET status='approved' WHERE id=? AND status='pending_approval'", (args.id,))
        db.commit()
    elif args.cmd == "send":
        for r in db.execute("SELECT * FROM outbox WHERE status='approved'").fetchall():
            lead = db.execute("SELECT opted_out FROM leads WHERE id=?", (r["lead_id"],)).fetchone() if r["lead_id"] else None
            try:
                if lead and lead["opted_out"]:
                    raise RuntimeError("lead opted out")
                whatsapp.send_text(r["recipient"], r["body"])
                db.execute("UPDATE outbox SET status='sent', sent_at=? WHERE id=?", (store.now(), r["id"]))
            except RuntimeError as exc:
                db.execute("UPDATE outbox SET status='failed', error=? WHERE id=?", (str(exc), r["id"]))
            db.commit()


if __name__ == "__main__":
    main()
