"""HTTP API for the web simulator.

POST /api/chat   {"text": "...", "history": [{"role", "text"}]} -> Server-Sent Events
POST /api/speak  {"text": "..."} -> audio/mpeg
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator

import uvicorn
from fastapi import FastAPI
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, Field

from homedocs_agent import aws, config
from homedocs_agent.agent import run_turn
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


@app.get("/api/health")
async def health() -> dict:
    return {"ok": True, "model": config.MODEL_ID, "mcp": config.MCP_URL}


def main() -> None:
    uvicorn.run(app, host=config.HOST, port=config.PORT)
