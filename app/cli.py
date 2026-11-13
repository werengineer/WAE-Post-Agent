"""Local operational commands. The combined agent is available through the API."""
import argparse
import json
import logging
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
import requests
from dotenv import load_dotenv
from app.tools.whatsapp import connect, approve, add_reminder


def social_main():
    from app.tools import social
    load_dotenv()
    parser = argparse.ArgumentParser(description="Company agent and social workflow")
    commands = parser.add_subparsers(dest="command", required=True)
    draft = commands.add_parser("draft")
    draft.add_argument("--topic", required=True)
    draft.add_argument("--platform", choices=social.LIMITS, default="linkedin")
    draft.add_argument("--company", type=Path, default=Path("company.json"))
    publish = commands.add_parser("publish")
    publish.add_argument("file", type=Path)
    direct = commands.add_parser("publish-direct", help="Publish a reviewed draft through the platform's own API (dry run unless --live)")
    direct.add_argument("file", type=Path)
    direct.add_argument("--live", action="store_true", help="Really send it to the platform")
    run = commands.add_parser("run", help="Ask the combined agent to use its tools")
    run.add_argument("message")
    args = parser.parse_args()
    try:
        if args.command == "publish":
            social.publish(args.file)
        elif args.command == "publish-direct":
            social.publish_direct(args.file, args.live)
        elif args.command == "run":
            from app.agent.core import run
            print(json.dumps(run(args.message), ensure_ascii=False, default=str))
        else:
            company = json.loads(args.company.read_text(encoding="utf-8"))
            if not company.get("name"):
                raise ValueError("Company profile needs a name")
            result = social.build_social_workflow().invoke({"company": company, "topic": args.topic, "platform": args.platform})
            print(result["text"])
            print(f"\nSaved draft: {result['output']}")
    except (ValueError, OSError, requests.RequestException) as exc:
        parser.exit(1, f"Error: {exc}\n")


def main():
    import sys
    if len(sys.argv) == 1 or sys.argv[1] in {"-h", "--help"}:
        parser = argparse.ArgumentParser(description="Shared company agent, WhatsApp operations, and social publishing")
        parser.add_argument("command", nargs="?", choices=["run", "serve", "draft", "publish", "publish-direct", "leads", "drafts", "approve", "reject", "remind", "reminders", "cancel-reminder", "notices"])
        parser.print_help()
        return
    if len(sys.argv) > 1 and sys.argv[1] in {"serve", "leads", "drafts", "reminders", "notices", "approve", "reject", "remind", "cancel-reminder"}:
        whatsapp_main()
    else:
        social_main()


def whatsapp_main():
    load_dotenv()
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    serve = commands.add_parser("serve")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)
    for name in ("leads", "drafts", "reminders", "notices"):
        commands.add_parser(name)
    approve_cmd = commands.add_parser("approve")
    approve_cmd.add_argument("id", type=int)
    approve_cmd.add_argument("--text", help="Replace draft with this exact reviewed text")
    reject = commands.add_parser("reject")
    reject.add_argument("id", type=int)
    remind = commands.add_parser("remind")
    remind.add_argument("--chat", required=True)
    remind.add_argument("--at", required=True, help="ISO date/time with timezone offset")
    remind.add_argument("--note", required=True)
    cancel = commands.add_parser("cancel-reminder")
    cancel.add_argument("id", type=int)
    args = parser.parse_args()
    try:
        with closing(connect()) as db:
            if args.command == "serve":
                import uvicorn
                from app.api.main import create_app
                uvicorn.run(create_app(), host=args.host, port=args.port, workers=1)
            elif args.command in {"leads", "drafts", "reminders", "notices"}:
                for row in db.execute(f"SELECT * FROM {args.command}"):
                    item = dict(row)
                    if "due" in item:
                        item["due"] = datetime.fromtimestamp(item["due"], timezone.utc).isoformat()
                    print(json.dumps(item, ensure_ascii=False))
            elif args.command == "approve":
                approve(db, args.id, args.text)
                print("Approved reply sent to OpenWA.")
            elif args.command == "reject":
                with db:
                    db.execute("UPDATE drafts SET state='rejected' WHERE id=? AND state='draft'", (args.id,))
            elif args.command == "remind":
                print("Reminder:", add_reminder(db, args.chat, args.at, args.note))
            elif args.command == "cancel-reminder":
                with db:
                    db.execute("UPDATE reminders SET state='cancelled' WHERE id=? AND state='pending'", (args.id,))
    except (ValueError, KeyError, OSError, requests.RequestException, RuntimeError) as exc:
        parser.exit(1, f"Error: {exc}\n")

