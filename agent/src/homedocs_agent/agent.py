"""One conversational turn: Bedrock Converse with MCP tools, streamed as events.

Events (plain dicts, sent to the browser as they happen):
  {"type": "tool_call",   "id", "name", "input"}
  {"type": "tool_result", "id", "name", "output", "is_error", "ms"}
  {"type": "answer",      "text"}
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator, Callable
from datetime import date
from typing import Any, Protocol

MAX_TOOL_ROUNDS = 5

SYSTEM_PROMPT = """You are a voice assistant like Alexa. You help the user with \
their household paperwork: bills, leases, warranties, insurance and ID documents.

Today is {today}.

Rules:
- Use the tools to look things up. Never guess a date, amount or term.
- Your answer is spoken aloud. Use one or two short sentences, no lists, no markdown.
- Say which document the answer came from, in plain words ("your lease says...").
- Say dates naturally ("November 14th") and mention how far away they are when useful.
- If the documents do not answer the question, say so briefly.
- "Notifications" means dates due in the next 14 days: use list_upcoming_dates with \
days_ahead 14 and mention each one briefly, soonest first.
- Only call save_document when the user asks you to remember something. Confirm what \
you saved in one sentence."""


class Toolbox(Protocol):
    converse_tools: list[dict[str, Any]]

    async def call(self, name: str, arguments: dict[str, Any]) -> tuple[dict[str, Any], bool]: ...


ConverseFn = Callable[..., dict[str, Any]]


def build_messages(history: list[dict[str, str]], user_text: str) -> list[dict[str, Any]]:
    """History is a list of {"role": "user"|"assistant", "text": ...} from the browser."""
    messages = [
        {"role": turn["role"], "content": [{"text": turn["text"]}]}
        for turn in history
        if turn.get("text")
    ]
    messages.append({"role": "user", "content": [{"text": user_text}]})
    return messages


async def run_turn(
    converse: ConverseFn,
    model_id: str,
    toolbox: Toolbox,
    history: list[dict[str, str]],
    user_text: str,
    today: date | None = None,
) -> AsyncIterator[dict[str, Any]]:
    messages = build_messages(history, user_text)
    system = [{"text": SYSTEM_PROMPT.format(today=(today or date.today()).strftime("%A, %B %d, %Y"))}]

    for _ in range(MAX_TOOL_ROUNDS + 1):
        # boto3 is synchronous; keep the event loop free while Bedrock thinks.
        response = await asyncio.to_thread(
            converse,
            modelId=model_id,
            system=system,
            messages=messages,
            toolConfig={"tools": toolbox.converse_tools},
            inferenceConfig={"maxTokens": 400, "temperature": 0.2},
        )
        message = response["output"]["message"]
        messages.append(message)

        if response["stopReason"] != "tool_use":
            text = " ".join(block["text"] for block in message["content"] if "text" in block)
            yield {"type": "answer", "text": text.strip()}
            return

        results = []
        for block in message["content"]:
            if "toolUse" not in block:
                continue
            use = block["toolUse"]
            yield {"type": "tool_call", "id": use["toolUseId"], "name": use["name"], "input": use["input"]}
            started = time.perf_counter()
            output, is_error = await toolbox.call(use["name"], use["input"])
            yield {
                "type": "tool_result",
                "id": use["toolUseId"],
                "name": use["name"],
                "output": output,
                "is_error": is_error,
                "ms": round((time.perf_counter() - started) * 1000),
            }
            results.append(
                {
                    "toolResult": {
                        "toolUseId": use["toolUseId"],
                        "content": [{"json": output}],
                        "status": "error" if is_error else "success",
                    }
                }
            )
        messages.append({"role": "user", "content": results})

    yield {"type": "answer", "text": "Sorry, I couldn't work that out. Try asking another way."}
