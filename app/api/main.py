"""FastAPI endpoints for the combined company agent and its workflows."""

import hashlib
import hmac
import json
import os
import sqlite3
from contextlib import closing
from typing import Annotated

from dotenv import load_dotenv
from fastapi import APIRouter, Body, Depends, FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, PlainTextResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field, StrictStr, field_validator
from starlette.concurrency import run_in_threadpool

from app.tools import whatsapp as bot
from app.api.operations import APIError, route
from app.services import cloudapi
from app.services.messaging import provider
from app.services.scheduler import lifespan


class ReplyEdit(BaseModel):
    text: StrictStr = Field(min_length=1)

    @field_validator("text")
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError("Text cannot be blank")
        return value


class Approval(BaseModel):
    text: StrictStr | None = None

    @field_validator("text")
    @classmethod
    def nonblank(cls, value):
        if value is None or not value.strip():
            raise ValueError("Omit text to approve saved text; replacement cannot be blank")
        return value


class ReminderCreate(BaseModel):
    chat: StrictStr = Field(min_length=1)
    at: StrictStr = Field(description="Future ISO datetime including timezone offset")
    note: StrictStr = Field(min_length=1)


class AgentRequest(BaseModel):
    message: StrictStr = Field(min_length=1, max_length=10000)


class SocialDraftRequest(BaseModel):
    platform: StrictStr
    topic: StrictStr = Field(min_length=1, max_length=10000)


class BodyLimitMiddleware:
    """Bound actual streamed bytes, including requests without Content-Length."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] not in {"POST", "PATCH"}:
            return await self.app(scope, receive, send)
        limit = 1048576 if scope["path"] in ("/openwa/webhook", "/whatsapp/webhook") else 65536
        chunks, size = [], 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            size += len(message.get("body", b""))
            if size > limit:
                response = JSONResponse({"error": "Request body too large"}, status_code=413)
                return await response(scope, receive, send)
            chunks.append(message.get("body", b""))
            if not message.get("more_body", False):
                break
        delivered = False

        async def replay():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": b"".join(chunks), "more_body": False}
            return await receive()

        await self.app(scope, replay, send)


bearer = HTTPBearer(auto_error=False)


def authenticate(credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]):
    token = os.getenv("WHATSAPP_API_TOKEN", "")
    if not token:
        raise APIError(503, "UI API disabled: configure WHATSAPP_API_TOKEN")
    if credentials is None or not hmac.compare_digest(credentials.credentials.encode(), token.encode()):
        raise APIError(401, "Invalid API token")


def dispatch(method, path, query=None, body=None):
    # A complete operation uses one connection on one worker thread.
    with closing(bot.connect()) as db:
        status, payload = route(db, method, path, query or {}, body or {})
    return JSONResponse(payload, status_code=status)


def create_app(*, run_worker=True):
    load_dotenv()


    app = FastAPI(title="Company Operations Agent", version="1.0.0", lifespan=lifespan)
    app.state.run_worker = run_worker
    app.add_middleware(BodyLimitMiddleware)
    origins = {x.strip() for x in os.getenv("WHATSAPP_API_ORIGINS", "").split(",") if x.strip()}

    @app.middleware("http")
    async def api_headers(request, call_next):
        origin = request.headers.get("origin")
        is_api = request.url.path.startswith("/api/")
        if is_api and origin and origin not in origins:
            response = JSONResponse({"error": "UI origin is not allowed"}, status_code=403)
        elif is_api and request.method == "OPTIONS":
            response = JSONResponse({"ok": True} if origin else {"error": "Preflight requires an Origin header"}, status_code=200 if origin else 400)
        else:
            response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        if is_api and origin in origins:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Vary"] = "Origin"
            response.headers["Access-Control-Allow-Headers"] = "Authorization, Content-Type"
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, PATCH, OPTIONS"
        return response

    @app.exception_handler(APIError)
    async def api_error(request, exc):
        return JSONResponse({"error": exc.message}, status_code=exc.status)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        return JSONResponse({"error": "Invalid request", "details": [
            {"location": list(x["loc"]), "message": x["msg"]} for x in exc.errors()
        ]}, status_code=400)

    @app.exception_handler(sqlite3.OperationalError)
    async def database_error(request, exc):
        return JSONResponse({"error": "Database busy or unavailable; refresh before retrying"}, status_code=503)

    @app.exception_handler(Exception)
    async def internal_error(request, exc):
        bot.LOG.error("HTTP request failed", exc_info=exc)
        return JSONResponse({"error": "Internal server error"}, status_code=500)

    api = APIRouter(prefix="/api", dependencies=[Depends(authenticate)])
    limit_type = Annotated[int, Query(ge=1, le=500)]
    offset_type = Annotated[int, Query(ge=0)]

    @api.get("/agent/tools", tags=["Agent"])
    def agent_tools():
        from app.tools.registry import TOOLS
        return {"tools": [{"name": t.name, "description": t.description, "parameters": t.args_schema.model_json_schema()} for t in TOOLS],
                "sending_requires_separate_approval": False,
                "publishing_requires_separate_approval": True,
                "operator_commands": ["send draft #<id>"],
                "whatsapp_send_requires_explicit_draft_id": True}

    @api.post("/agent/run", tags=["Agent"])
    def agent_run(body: AgentRequest):
        from app.agent.core import run
        from langgraph.errors import GraphRecursionError
        try:
            return run(body.message)
        except GraphRecursionError:
            raise APIError(409, "Agent step limit reached. Some tools may have completed; inspect records before retrying.")

    @api.get("/posts", tags=["Social"])
    def posts():
        from app.tools.registry import list_social_drafts
        items = list_social_drafts.invoke({})
        return {"items": items}

    @api.post("/posts/draft", status_code=201, tags=["Social"])
    def social_draft(body: SocialDraftRequest):
        from app.tools.registry import draft_social_post
        try:
            return draft_social_post.invoke(body.model_dump())
        except ValueError as exc:
            raise APIError(400, str(exc))

    @api.post("/posts/{post_id}/publish", tags=["Social"])
    def publish_post(post_id: str):
        from uuid import UUID
        from pathlib import Path
        from app.tools.social import publish
        try:
            name = str(UUID(post_id))
        except ValueError:
            raise APIError(400, "Invalid post id")
        path = Path("posts") / f"{name}.json"
        if not path.is_file():
            raise APIError(404, "Post not found")
        try:
            publish(path)
        except ValueError as exc:
            raise APIError(409, str(exc))
        return json.loads(path.read_text(encoding="utf-8"))

    @api.get("/status", tags=["Connection"])
    def status():
        return dispatch("GET", "/api/status")

    def listing(resource, limit, offset, state=None):
        query = {"limit": [str(limit)], "offset": [str(offset)]}
        if state is not None:
            query["state"] = [state]
        return dispatch("GET", f"/api/{resource}", query)

    @api.get("/leads", tags=["Leads"])
    def leads(limit: limit_type = 100, offset: offset_type = 0):
        return listing("leads", limit, offset)

    @api.get("/leads/{chat_id}/messages", tags=["Leads"])
    def messages(chat_id: str, limit: limit_type = 100, offset: offset_type = 0):
        return dispatch("GET", f"/api/leads/{chat_id}/messages", {"limit": [str(limit)], "offset": [str(offset)]})

    @api.get("/drafts", tags=["Drafts"])
    def drafts(limit: limit_type = 100, offset: offset_type = 0, state: str | None = None):
        return listing("drafts", limit, offset, state)

    @api.get("/drafts/{draft_id}", tags=["Drafts"])
    def draft(draft_id: int):
        return dispatch("GET", f"/api/drafts/{draft_id}")

    @api.patch("/drafts/{draft_id}", tags=["Drafts"])
    def edit(draft_id: int, body: ReplyEdit):
        return dispatch("PATCH", f"/api/drafts/{draft_id}", body=body.model_dump())

    @api.post("/drafts/{draft_id}/approve", tags=["Drafts"])
    def approve(draft_id: int, body: Approval = Body(default_factory=Approval)):
        return dispatch("POST", f"/api/drafts/{draft_id}/approve", body=body.model_dump(exclude_unset=True))

    @api.post("/drafts/{draft_id}/reject", tags=["Drafts"])
    def reject(draft_id: int):
        return dispatch("POST", f"/api/drafts/{draft_id}/reject")

    @api.get("/reminders", tags=["Reminders"])
    def reminders(limit: limit_type = 100, offset: offset_type = 0, state: str | None = None):
        return listing("reminders", limit, offset, state)

    @api.post("/reminders", status_code=201, tags=["Reminders"])
    def create_reminder(body: ReminderCreate):
        return dispatch("POST", "/api/reminders", body=body.model_dump())

    @api.post("/reminders/{reminder_id}/cancel", tags=["Reminders"])
    def cancel(reminder_id: int):
        return dispatch("POST", f"/api/reminders/{reminder_id}/cancel")

    app.include_router(api)

    @app.post("/openwa/webhook", tags=["OpenWA"])
    async def webhook(request: Request):
        raw = await request.body()
        secret = os.getenv("OPENWA_WEBHOOK_SECRET", "")
        expected = "sha256=" + hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
        signature = request.headers.get("X-OpenWA-Signature", "")
        if not secret or not hmac.compare_digest(expected.encode(), signature.encode()):
            raise APIError(401, "Invalid webhook signature")
        try:
            event = json.loads(raw)
        except (ValueError, UnicodeError):
            raise APIError(400, "Invalid webhook JSON")

        def store():
            with closing(bot.connect()) as db:
                try:
                    bot.accept(db, event)
                except (ValueError, KeyError, TypeError):
                    raise APIError(400, "Invalid webhook event")

        await run_in_threadpool(store)
        return PlainTextResponse("OK")

    # Meta's WhatsApp Cloud API (WHATSAPP_PROVIDER=cloud): one-time URL check, then signed message calls
    @app.get("/whatsapp/webhook", tags=["WhatsApp Cloud API"])
    async def cloud_verify(request: Request):
        query, token = request.query_params, os.getenv("WHATSAPP_VERIFY_TOKEN", "")
        if (provider() == "cloud" and token and query.get("hub.mode") == "subscribe"
                and hmac.compare_digest(query.get("hub.verify_token", "").encode(), token.encode())):
            return PlainTextResponse(query.get("hub.challenge", ""))
        raise APIError(403, "Webhook verification failed")

    @app.post("/whatsapp/webhook", tags=["WhatsApp Cloud API"])
    async def cloud_webhook(request: Request):
        if provider() != "cloud":
            raise APIError(404, "Not found")
        raw = await request.body()
        if not cloudapi.verify_signature(raw, request.headers.get("X-Hub-Signature-256", "")):
            raise APIError(401, "Invalid webhook signature")
        try:
            found = cloudapi.events(json.loads(raw))
        except (ValueError, UnicodeError):
            raise APIError(400, "Invalid webhook JSON")
        # one Meta app can carry several numbers: only messages to OUR number are ours; the rest is acknowledged and dropped
        phone_id = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "")
        mine = [event for event in found if event["sessionId"] == phone_id]

        def store():
            with closing(bot.connect()) as db:
                for event in mine:
                    try:
                        bot.accept(db, event)
                    except (ValueError, KeyError, TypeError):
                        bot.LOG.warning("Ignored an invalid WhatsApp message event")  # 200 anyway: Meta would retry it for days

        await run_in_threadpool(store)
        return PlainTextResponse("OK")

    return app


app = create_app()
