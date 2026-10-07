"""The tool loop, with a scripted fake of Bedrock ConverseStream and a fake toolbox."""

import asyncio
import copy
import json
from datetime import date

from homedocs_agent.agent import build_messages, run_turn


class FakeToolbox:
    converse_tools = [{"toolSpec": {"name": "list_upcoming_dates", "description": "d", "inputSchema": {"json": {}}}}]

    def __init__(self):
        self.calls = []
        self.context = {}

    async def call(self, name, arguments):
        self.calls.append((name, {**arguments, **self.context}))
        return {"result": [{"title": "Internet bill", "date": "2026-10-15"}]}, False


def stream_of(content, stop_reason):
    """Turn a finished assistant message into ConverseStream events."""
    events = [{"messageStart": {"role": "assistant"}}]
    for index, block in enumerate(content):
        if "text" in block:
            # Split text in two to check that deltas are joined back together.
            half = len(block["text"]) // 2
            for piece in (block["text"][:half], block["text"][half:]):
                events.append({"contentBlockDelta": {"contentBlockIndex": index, "delta": {"text": piece}}})
        else:
            use = block["toolUse"]
            events.append({"contentBlockStart": {"contentBlockIndex": index, "start": {"toolUse": {"toolUseId": use["toolUseId"], "name": use["name"]}}}})
            events.append({"contentBlockDelta": {"contentBlockIndex": index, "delta": {"toolUse": {"input": json.dumps(use["input"])}}}})
        events.append({"contentBlockStop": {"contentBlockIndex": index}})
    events.append({"messageStop": {"stopReason": stop_reason}})
    return {"stream": iter(events)}


def scripted(*rounds):
    seen = []

    def converse_stream(**kwargs):
        # Snapshot: run_turn keeps appending to the same messages list.
        seen.append(copy.deepcopy(kwargs))
        content, stop_reason = rounds[len(seen) - 1]
        return stream_of(content, stop_reason)

    return converse_stream, seen


def collect(gen):
    async def run():
        return [e async for e in gen]

    return asyncio.run(run())


TOOL_USE = ([{"toolUse": {"toolUseId": "t1", "name": "list_upcoming_dates", "input": {"days_ahead": 30}}}], "tool_use")
ANSWER = ([{"text": "Your internet bill is due October 15th."}], "end_turn")


def test_tool_round_then_streamed_answer():
    converse_stream, seen = scripted(TOOL_USE, ANSWER)
    toolbox = FakeToolbox()
    events = collect(run_turn(converse_stream, "model", toolbox, [], "what's due soon?", today=date(2026, 10, 6)))

    assert [e["type"] for e in events] == ["tool_call", "tool_result", "answer_delta", "answer_delta", "answer"]
    assert "".join(e["text"] for e in events if e["type"] == "answer_delta") == "Your internet bill is due October 15th."
    assert events[-1]["text"] == "Your internet bill is due October 15th."
    # The user's date reaches the tool and the system prompt.
    assert toolbox.calls == [("list_upcoming_dates", {"days_ahead": 30, "today": "2026-10-06"})]
    assert "Tuesday, October 06, 2026" in seen[0]["system"][0]["text"]
    # The second Bedrock call carries the tool result back to the model.
    assert seen[1]["messages"][-1]["content"][0]["toolResult"]["toolUseId"] == "t1"
    assert seen[1]["messages"][-2]["content"][0]["toolUse"]["input"] == {"days_ahead": 30}


def test_text_from_several_rounds_is_joined_with_a_space():
    first = ([{"text": "One moment."}, TOOL_USE[0][0]], "tool_use")
    converse_stream, _ = scripted(first, ANSWER)
    events = collect(run_turn(converse_stream, "model", FakeToolbox(), [], "q"))
    assert events[-1]["text"] == "One moment. Your internet bill is due October 15th."


def test_gives_up_after_too_many_tool_rounds():
    converse_stream, _ = scripted(*([TOOL_USE] * 10))
    events = collect(run_turn(converse_stream, "model", FakeToolbox(), [], "loop forever"))
    assert events[-1]["type"] == "answer"
    assert events[-1]["text"].startswith("Sorry")


def test_build_messages_skips_empty_turns():
    messages = build_messages([{"role": "user", "text": "hi"}, {"role": "assistant", "text": ""}], "next")
    assert [m["content"][0]["text"] for m in messages] == ["hi", "next"]
