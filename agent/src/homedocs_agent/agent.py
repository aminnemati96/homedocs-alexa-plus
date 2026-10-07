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

SYSTEM_PROMPT = """You are a voice assistant like Alexa, running on the user's device. Today is {today} (the user's local date).

{skill}"""

# Used only if the MCP server doesn't publish its Agent Skill.
FALLBACK_SKILL = """Help the user with their household paperwork using the tools. Never guess a date, amount or term. Answer in one or two short spoken sentences, say which document the answer came from, and only save or delete documents when the user asks."""


class Toolbox(Protocol):
    converse_tools: list[dict[str, Any]]
    context: dict[str, Any]
    skill: str

    async def call(self, name: str, arguments: dict[str, Any]) -> tuple[dict[str, Any], bool]: ...


ConverseStreamFn = Callable[..., dict[str, Any]]


MAX_HISTORY_TURNS = 20


def build_messages(history: list[dict[str, str]], user_text: str) -> list[dict[str, Any]]:
    """History is a list of {"role": "user"|"assistant", "text": ...} from the browser.

    Converse requires the conversation to start with the user and alternate
    roles, but the browser's history can break that: a failed upload or an error
    leaves two user turns in a row. Consecutive turns from the same role are
    merged, and only the most recent turns are kept.
    """
    turns = [t for t in history if t.get("text")][-MAX_HISTORY_TURNS:]
    turns.append({"role": "user", "text": user_text})
    messages: list[dict[str, Any]] = []
    for turn in turns:
        if messages and messages[-1]["role"] == turn["role"]:
            messages[-1]["content"][0]["text"] += "\n" + turn["text"]
        else:
            messages.append({"role": turn["role"], "content": [{"text": turn["text"]}]})
    while messages and messages[0]["role"] != "user":
        messages.pop(0)
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
    # The instructions come from the MCP server's Agent Skill (SKILL.md), so the
    # same guide serves this agent, Alexa+ and any other MCP client.
    skill = getattr(toolbox, "skill", "") or FALLBACK_SKILL
    system = [{"text": SYSTEM_PROMPT.format(today=today.strftime("%A, %B %d, %Y"), skill=skill)}]
    spoken: list[str] = []

    for round_number in range(MAX_TOOL_ROUNDS + 1):
        # The first round must call a tool, so every answer is grounded in the
        # user's documents instead of the model's memory of the conversation
        # (which once produced a renewal date that exists in no document).
        tool_config: dict[str, Any] = {"tools": toolbox.converse_tools}
        if round_number == 0:
            tool_config["toolChoice"] = {"any": {}}
        texts: dict[int, str] = {}
        tools: dict[int, dict[str, Any]] = {}
        stop_reason = None
        async for event in stream_events(
            converse_stream,
            modelId=model_id,
            system=system,
            messages=messages,
            toolConfig=tool_config,
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
