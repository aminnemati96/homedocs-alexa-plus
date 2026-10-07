"""HTTP API for the web simulator.

POST /api/chat   {"text": "...", "history": [{"role", "text"}]} -> Server-Sent Events
POST /api/speak  {"text": "..."} -> audio/mpeg
POST /api/documents  multipart file (PDF or image) -> extracted and saved document
"""

from __future__ import annotations

import asyncio
import hmac
import json
import logging
import time
from collections.abc import AsyncIterator
from datetime import date

import uvicorn
from fastapi import FastAPI, Form, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse, Response, StreamingResponse
from pydantic import BaseModel, Field

from homedocs_agent import aws, config
from homedocs_agent.agent import run_turn
from homedocs_agent.extract import UnsupportedFile, extract
from homedocs_agent.connection import open_mcp

app = FastAPI(title="homedocs agent")
log = logging.getLogger("homedocs")

# Every failed request logs one line starting with this marker; a CloudWatch
# metric filter counts them and alarms (see infra/alerts.tf).
FAILURE_MARKER = "HOMEDOCS_FAILURE"

# The Lambda Web Adapter forwards non-HTTP events (our EventBridge schedule) here.
WARMUP_PATH = "/events"


@app.middleware("http")
async def guard(request: Request, call_next):
    """Public-deployment checks; both are skipped when their setting is empty.

    /events is exempt because scheduled warm-ups reach it through a direct Lambda
    invoke, not CloudFront; it checks its own token instead (see warmup()).
    """
    if request.url.path not in ("/api/health", WARMUP_PATH):
        if config.ORIGIN_SECRET and not hmac.compare_digest(
            request.headers.get("x-origin-verify", ""), config.ORIGIN_SECRET
        ):
            return JSONResponse({"detail": "Forbidden"}, status_code=403)
        if config.DEMO_PASSCODE and not hmac.compare_digest(
            request.headers.get("x-demo-passcode", ""), config.DEMO_PASSCODE
        ):
            return JSONResponse({"detail": "Passcode required"}, status_code=401)
    return await call_next(request)


class Turn(BaseModel):
    role: str = Field(pattern="^(user|assistant)$")
    text: str


class ChatRequest(BaseModel):
    text: str = Field(min_length=1, max_length=1000)
    # Long conversations are fine: run_turn keeps only the most recent turns.
    history: list[Turn] = Field(default_factory=list, max_length=200)
    # The browser's local date. Servers run on UTC, which is already tomorrow
    # for North American users in the evening.
    today: date | None = None


def _local_today(today: date | None) -> date:
    """The user's date if the browser sent a plausible one, else the server's."""
    server = date.today()
    if today is not None and abs((today - server).days) <= 1:
        return today
    return server


class SpeakRequest(BaseModel):
    text: str = Field(min_length=1, max_length=1500)


def _sse(event: dict) -> str:
    return f"data: {json.dumps(event, default=str)}\n\n"


async def _chat_events(request: ChatRequest) -> AsyncIterator[str]:
    try:
        async with open_mcp() as toolbox:
            async for event in run_turn(
                aws.bedrock().converse_stream,
                config.MODEL_ID,
                toolbox,
                [t.model_dump() for t in request.history],
                request.text,
                today=_local_today(request.today),
            ):
                yield _sse(event)
    except Exception as e:  # surface failures in the UI instead of a dropped stream
        yield _sse({"type": "error", "message": _failure("chat", e)})


def _failure(where: str, e: BaseException) -> str:
    """Log a failed request for the CloudWatch alarm; return the message for the user."""
    message = str(_root_cause(e))
    log.error("%s %s: %s", FAILURE_MARKER, where, message)
    return message


def _root_cause(e: BaseException) -> BaseException:
    """The MCP client wraps errors in (nested) ExceptionGroups; find the real one."""
    while isinstance(e, BaseExceptionGroup) and e.exceptions:
        e = e.exceptions[0]
    return e


@app.post("/api/chat")
async def chat(request: ChatRequest) -> StreamingResponse:
    return StreamingResponse(_chat_events(request), media_type="text/event-stream")


@app.post("/api/speak")
async def speak(request: SpeakRequest) -> Response:
    audio = await asyncio.to_thread(aws.synthesize, request.text)
    return Response(content=audio, media_type="audio/mpeg")


def _confirmation(doc: dict, today: date) -> str:
    """What the assistant says after saving, e.g. "Got it, I saved your lease..."."""
    message = f"Got it, I saved your {doc['title']}."
    upcoming = sorted(
        (d for d in doc.get("key_dates", []) if date.fromisoformat(d["date"]) >= today),
        key=lambda d: d["date"],
    )
    if upcoming:
        first = upcoming[0]
        when = date.fromisoformat(first["date"]).strftime("%B %d, %Y").replace(" 0", " ")
        message += f" {first['label']} is on {when}, and I'll remind you before then."
    return message


@app.post("/api/documents")
async def add_document(file: UploadFile, today: date | None = Form(None)) -> dict:
    """Extract a document's fields with Bedrock, then save it through the MCP server.

    Returns both steps so the UI can show them in the tool panel.
    """
    local_today = _local_today(today)
    data = await file.read()
    content_type = file.content_type or ""
    try:
        started = time.perf_counter()
        fields = await asyncio.to_thread(
            extract, aws.bedrock().converse, config.MODEL_ID, content_type, data, local_today
        )
        extract_ms = round((time.perf_counter() - started) * 1000)

        started = time.perf_counter()
        async with open_mcp() as toolbox:
            saved, is_error = await toolbox.call("save_document", fields)
        save_ms = round((time.perf_counter() - started) * 1000)
    except UnsupportedFile as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=502, detail=_failure("upload", e)) from e
    if is_error:
        raise HTTPException(status_code=502, detail=saved.get("text", "Saving failed"))

    return {
        "steps": [
            {"name": "bedrock_extract", "input": {"file": file.filename, "type": content_type},
             "output": fields, "ms": extract_ms},
            {"name": "save_document", "input": {"title": fields["title"]}, "output": saved, "ms": save_ms},
        ],
        "message": _confirmation(saved, local_today),
    }


NOTIFY_DAYS = 14


@app.get("/api/notifications")
async def notifications(today: date | None = None) -> dict:
    """Dates due in the next two weeks, straight from the MCP server.

    The web page lights the ring yellow when this is not empty, like an Echo
    with a pending notification. No model call, so it is instant and free.
    """
    started = time.perf_counter()
    try:
        async with open_mcp() as toolbox:
            result, is_error = await toolbox.call(
                "list_upcoming_dates",
                {"days_ahead": NOTIFY_DAYS, "today": _local_today(today).isoformat()},
            )
    except Exception as e:
        raise HTTPException(status_code=502, detail=_failure("notifications", e)) from e
    if is_error:
        raise HTTPException(status_code=502, detail=result.get("text", "Lookup failed"))
    return {
        "items": result.get("result", []),
        "tool": {
            "name": "list_upcoming_dates",
            "input": {"days_ahead": NOTIFY_DAYS},
            "output": result,
            "ms": round((time.perf_counter() - started) * 1000),
        },
    }


@app.post(WARMUP_PATH)
async def scheduled_task(request: Request) -> dict:
    """Jobs run by EventBridge Scheduler through a direct Lambda invoke.

    Payload: {"task": "warmup" | "reset", "token": <origin secret>}
    - warmup (every 5 minutes): the same MCP call as the notification check, so
      the Lambda and its AgentCore session are already running for visitors.
    - reset (nightly): put the demo documents back to the samples, so one
      visitor's uploads don't stay for the next (admin tool, hidden from the model).
    """
    body = await request.json() if await request.body() else {}
    body = body if isinstance(body, dict) else {}
    token = body.get("token", "")
    if not config.ORIGIN_SECRET or not hmac.compare_digest(str(token), config.ORIGIN_SECRET):
        raise HTTPException(status_code=403, detail="Forbidden")
    task = body.get("task", "warmup")
    if task not in ("warmup", "reset"):
        raise HTTPException(status_code=400, detail=f"Unknown task '{task}'")

    started = time.perf_counter()
    try:
        async with open_mcp() as toolbox:
            if task == "reset":
                result, is_error = await toolbox.call("admin_reset_demo", {})
                if is_error:
                    raise RuntimeError(result.get("text", "Reset failed"))
            else:
                result, _ = await toolbox.call("list_upcoming_dates", {"days_ahead": NOTIFY_DAYS})
    except Exception as e:
        raise HTTPException(status_code=502, detail=_failure(task, e)) from e
    log.info("%s done in %d ms", task, round((time.perf_counter() - started) * 1000))
    return {"ok": True, "task": task}


@app.get("/api/health")
async def health() -> dict:
    return {"ok": True, "model": config.MODEL_ID, "mcp": config.MCP_URL}


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    uvicorn.run(app, host=config.HOST, port=config.PORT)
