"""HTTP API for the web simulator.

POST /api/chat   {"text": "...", "history": [{"role", "text"}]} -> Server-Sent Events
POST /api/speak  {"text": "..."} -> audio/mpeg
POST /api/documents  multipart file (PDF or image) -> extracted and saved document
"""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import AsyncIterator
from datetime import date

import uvicorn
from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, Field

from homedocs_agent import aws, config
from homedocs_agent.agent import run_turn
from homedocs_agent.extract import UnsupportedFile, extract
from homedocs_agent.mcp_tools import open_toolbox

app = FastAPI(title="homedocs agent")


class Turn(BaseModel):
    role: str = Field(pattern="^(user|assistant)$")
    text: str


class ChatRequest(BaseModel):
    text: str = Field(min_length=1, max_length=1000)
    history: list[Turn] = Field(default_factory=list, max_length=20)


class SpeakRequest(BaseModel):
    text: str = Field(min_length=1, max_length=1500)


def _sse(event: dict) -> str:
    return f"data: {json.dumps(event, default=str)}\n\n"


async def _chat_events(request: ChatRequest) -> AsyncIterator[str]:
    try:
        async with open_toolbox(config.MCP_URL) as toolbox:
            async for event in run_turn(
                aws.bedrock.converse,
                config.MODEL_ID,
                toolbox,
                [t.model_dump() for t in request.history],
                request.text,
            ):
                yield _sse(event)
    except Exception as e:  # surface failures in the UI instead of a dropped stream
        yield _sse({"type": "error", "message": str(_root_cause(e))})


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


def _confirmation(doc: dict) -> str:
    """What the assistant says after saving, e.g. "Got it, I saved your lease..."."""
    message = f"Got it, I saved your {doc['title']}."
    upcoming = sorted(
        (d for d in doc.get("key_dates", []) if date.fromisoformat(d["date"]) >= date.today()),
        key=lambda d: d["date"],
    )
    if upcoming:
        first = upcoming[0]
        when = date.fromisoformat(first["date"]).strftime("%B %d, %Y").replace(" 0", " ")
        message += f" {first['label']} is on {when}, and I'll remind you before then."
    return message


@app.post("/api/documents")
async def add_document(file: UploadFile) -> dict:
    """Extract a document's fields with Bedrock, then save it through the MCP server.

    Returns both steps so the UI can show them in the tool panel.
    """
    data = await file.read()
    content_type = file.content_type or ""
    try:
        started = time.perf_counter()
        fields = await asyncio.to_thread(extract, aws.bedrock.converse, config.MODEL_ID, content_type, data)
        extract_ms = round((time.perf_counter() - started) * 1000)

        started = time.perf_counter()
        async with open_toolbox(config.MCP_URL) as toolbox:
            saved, is_error = await toolbox.call("save_document", fields)
        save_ms = round((time.perf_counter() - started) * 1000)
    except UnsupportedFile as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(_root_cause(e))) from e
    if is_error:
        raise HTTPException(status_code=502, detail=saved.get("text", "Saving failed"))

    return {
        "steps": [
            {"name": "bedrock_extract", "input": {"file": file.filename, "type": content_type},
             "output": fields, "ms": extract_ms},
            {"name": "save_document", "input": {"title": fields["title"]}, "output": saved, "ms": save_ms},
        ],
        "message": _confirmation(saved),
    }


@app.get("/api/health")
async def health() -> dict:
    return {"ok": True, "model": config.MODEL_ID, "mcp": config.MCP_URL}


def main() -> None:
    uvicorn.run(app, host=config.HOST, port=config.PORT)
