"""Background inbox processing and reminder delivery, owned by the app lifespan."""
import os
import threading
import time
from contextlib import asynccontextmanager, closing
from starlette.concurrency import run_in_threadpool
from app.tools import whatsapp as bot
from app.services.chat_policy import unrestricted
from app.services.messaging import provider


def tick(db):
    from app.agent.core import process_incoming
    process_incoming(db)
    for row in db.execute("SELECT * FROM notices WHERE state='pending'").fetchall():
        bot.deliver(db, "notices", row, row["text"])
    for row in db.execute("SELECT * FROM reminders WHERE state='pending' AND due<=?", (time.time(),)).fetchall():
        bot.deliver(db, "reminders", row, f"Follow up: {row['chat']}\n{row['note']}")


@asynccontextmanager
async def lifespan(app):
    if not app.state.run_worker:
        yield
        return
    if provider() == "cloud":
        required, secret = ("WHATSAPP_PHONE_NUMBER_ID", "WHATSAPP_ACCESS_TOKEN", "WHATSAPP_APP_SECRET",
                            "WHATSAPP_VERIFY_TOKEN", "OPENWA_OWNER_CHAT_ID", "GROQ_API_KEY"), "WHATSAPP_VERIFY_TOKEN"
    else:
        required, secret = ("OPENWA_BASE_URL", "OPENWA_API_KEY", "OPENWA_SESSION_ID",
                            "OPENWA_OWNER_CHAT_ID", "OPENWA_WEBHOOK_SECRET", "GROQ_API_KEY"), "OPENWA_WEBHOOK_SECRET"
    for key in required:
        if not os.getenv(key):
            raise ValueError(f"Set {key} in .env")
    if len(os.environ[secret]) < 16:
        raise ValueError(f"{secret} must be at least 16 characters")
    if not unrestricted() and not os.getenv("OPENWA_TEST_CHAT_ID", "").strip():
        bot.LOG.warning("No OPENWA_TEST_CHAT_ID set: all customer chats are blocked")
    with closing(bot.connect()) as db, db:
        for table in ("drafts", "reminders", "notices"):
            db.execute(f"UPDATE {table} SET state='uncertain' WHERE state='sending'")
    stop = threading.Event()

    def worker():
        with closing(bot.connect()) as db:
            while not stop.is_set():
                try:
                    tick(db)
                except Exception:
                    bot.LOG.exception("Worker failed; trying again next cycle")
                stop.wait(5)

    thread = threading.Thread(target=worker, name="whatsapp-worker", daemon=True)
    thread.start()
    app.state.worker_thread = thread
    try:
        yield
    finally:
        stop.set()
        await run_in_threadpool(thread.join)
