"""One conversational turn: Bedrock ConverseStream with MCP tools, streamed as events.

Events (plain dicts, sent to the browser as they happen):
  {"type": "answer_delta", "text"}           a piece of the spoken answer, as Claude writes it
  {"type": "tool_call",    "id", "name", "input"}
  {"type": "tool_result",  "id", "name", "output", "is_error", "ms"}
  {"type": "answer",       "text"}           the complete answer, last event of the turn

Streaming lets the browser show and speak the first sentence while the rest is
still being written, which matters most for a voice assistant.
"""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import AsyncIterator, Callable
from datetime import date
from typing import Any, Protocol

MAX_TOOL_ROUNDS = 5

SYSTEM_PROMPT = """You are a voice assistant like Alexa. You help the user with \
their household paperwork: bills, leases, warranties, insurance and ID documents.

Today is {today} (the user's local date).

Rules:
- Use the tools to look things up. Never guess a date, amount or term.
- Don't announce that you are looking something up; just answer.
- Your answer is spoken aloud. Use one or two short sentences, no lists, no markdown.
- Say which document the answer came from, in plain words ("your lease says...").
- Say dates naturally ("November 14th") and mention how far away they are when useful.
- If the documents do not answer the question, say so briefly.
- "Notifications" means dates due in the next 14 days (list_upcoming_dates with \
days_ahead 14). If the user asks for anything beyond their notifications, look \
further ahead (for example 90 days) and mention only what they haven't heard yet.
- Only call save_document when the user asks you to remember something, and \
delete_document when they clearly ask you to forget or remove something. Confirm \
what you saved or removed in one sentence."""


class Toolbox(Protocol):
    converse_tools: list[dict[str, Any]]
    context: dict[str, Any]

    async def call(self, name: str, arguments: dict[str, Any]) -> tuple[dict[str, Any], bool]: ...


ConverseStreamFn = Callable[..., dict[str, Any]]


def build_messages(history: list[dict[str, str]], user_text: str) -> list[dict[str, Any]]:
    """History is a list of {"role": "user"|"assistant", "text": ...} from the browser."""
    messages = [
        {"role": turn["role"], "content": [{"text": turn["text"]}]}
        for turn in history
        if turn.get("text")
    ]
    messages.append({"role": "user", "content": [{"text": user_text}]})
    return messages


async def stream_events(converse_stream: ConverseStreamFn, **kwargs: Any) -> AsyncIterator[dict[str, Any]]:
    """Run boto3's blocking ConverseStream in a thread and yield its events here."""
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue[Any] = asyncio.Queue()
    done = object()

    def pump() -> None:
        try:
            for event in converse_stream(**kwargs)["stream"]:
                loop.call_soon_threadsafe(queue.put_nowait, event)
        except Exception as e:  # handed to the async side and re-raised there
            loop.call_soon_threadsafe(queue.put_nowait, e)
        finally:
            loop.call_soon_threadsafe(queue.put_nowait, done)

    worker = loop.run_in_executor(None, pump)
    while (item := await queue.get()) is not done:
        if isinstance(item, Exception):
            raise item
        yield item
    await worker


async def run_turn(
    converse_stream: ConverseStreamFn,
    model_id: str,
    toolbox: Toolbox,
    history: list[dict[str, str]],
    user_text: str,
    today: date | None = None,
) -> AsyncIterator[dict[str, Any]]:
    today = today or date.today()
    # Tools that take the user's date get it from us, not from the model.
    toolbox.context["today"] = today.isoformat()
    messages = build_messages(history, user_text)
    system = [{"text": SYSTEM_PROMPT.format(today=today.strftime("%A, %B %d, %Y"))}]
    spoken: list[str] = []

    for _ in range(MAX_TOOL_ROUNDS + 1):
        texts: dict[int, str] = {}
        tools: dict[int, dict[str, Any]] = {}
        stop_reason = None
        async for event in stream_events(
            converse_stream,
            modelId=model_id,
            system=system,
            messages=messages,
            toolConfig={"tools": toolbox.converse_tools},
            inferenceConfig={"maxTokens": 400, "temperature": 0.2},
        ):
            if "contentBlockStart" in event:
                start = event["contentBlockStart"]
                if "toolUse" in start["start"]:
                    use = start["start"]["toolUse"]
                    tools[start["contentBlockIndex"]] = {"id": use["toolUseId"], "name": use["name"], "json": ""}
            elif "contentBlockDelta" in event:
                index = event["contentBlockDelta"]["contentBlockIndex"]
                delta = event["contentBlockDelta"]["delta"]
                if "text" in delta:
                    piece = delta["text"]
                    if not texts and spoken and piece.strip():
                        piece = " " + piece.lstrip()  # space between rounds' text
                    texts[index] = texts.get(index, "") + piece
                    yield {"type": "answer_delta", "text": piece}
                elif "toolUse" in delta:
                    tools[index]["json"] += delta["toolUse"]["input"]
            elif "messageStop" in event:
                stop_reason = event["messageStop"]["stopReason"]

        # Rebuild the assistant message in block order for the conversation.
        content: list[dict[str, Any]] = []
        for index in sorted(texts.keys() | tools.keys()):
            if index in texts and texts[index].strip():
                content.append({"text": texts[index]})
            elif index in tools:
                tool = tools[index]
                tool["input"] = json.loads(tool["json"] or "{}")
                content.append({"toolUse": {"toolUseId": tool["id"], "name": tool["name"], "input": tool["input"]}})
        spoken.extend(texts[i] for i in sorted(texts) if texts[i].strip())
        if content:
            messages.append({"role": "assistant", "content": content})

        if stop_reason != "tool_use":
            yield {"type": "answer", "text": "".join(spoken).strip()}
            return

        results = []
        for index in sorted(tools):
            tool = tools[index]
            yield {"type": "tool_call", "id": tool["id"], "name": tool["name"], "input": tool["input"]}
            started = time.perf_counter()
            output, is_error = await toolbox.call(tool["name"], tool["input"])
            yield {
                "type": "tool_result",
                "id": tool["id"],
                "name": tool["name"],
                "output": output,
                "is_error": is_error,
                "ms": round((time.perf_counter() - started) * 1000),
            }
            results.append(
                {
                    "toolResult": {
                        "toolUseId": tool["id"],
                        "content": [{"json": output}],
                        "status": "error" if is_error else "success",
                    }
                }
            )
        messages.append({"role": "user", "content": results})

    sorry = "Sorry, I couldn't work that out. Try asking another way."
    yield {"type": "answer_delta", "text": sorry}
    yield {"type": "answer", "text": sorry}
