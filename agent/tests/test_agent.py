"""The tool loop, with a scripted fake of Bedrock Converse and a fake toolbox."""

import asyncio
import copy
from datetime import date

from homedocs_agent.agent import build_messages, run_turn


class FakeToolbox:
    converse_tools = [{"toolSpec": {"name": "list_upcoming_dates", "description": "d", "inputSchema": {"json": {}}}}]

    def __init__(self):
        self.calls = []

    async def call(self, name, arguments):
        self.calls.append((name, arguments))
        return {"result": [{"title": "Internet bill", "date": "2026-10-15"}]}, False


def scripted_converse(*responses):
    seen = []

    def converse(**kwargs):
        # Snapshot: run_turn keeps appending to the same messages list.
        seen.append(copy.deepcopy(kwargs))
        return responses[len(seen) - 1]

    return converse, seen


def collect(gen):
    async def run():
        return [e async for e in gen]

    return asyncio.run(run())


TOOL_USE = {
    "stopReason": "tool_use",
    "output": {"message": {"role": "assistant", "content": [
        {"toolUse": {"toolUseId": "t1", "name": "list_upcoming_dates", "input": {"days_ahead": 30}}}
    ]}},
}
ANSWER = {
    "stopReason": "end_turn",
    "output": {"message": {"role": "assistant", "content": [{"text": "Your internet bill is due October 15th."}]}},
}


def test_tool_round_then_answer():
    converse, seen = scripted_converse(TOOL_USE, ANSWER)
    toolbox = FakeToolbox()
    events = collect(run_turn(converse, "model", toolbox, [], "what's due soon?", today=date(2026, 10, 6)))

    assert [e["type"] for e in events] == ["tool_call", "tool_result", "answer"]
    assert toolbox.calls == [("list_upcoming_dates", {"days_ahead": 30})]
    assert events[-1]["text"] == "Your internet bill is due October 15th."
    # The second Bedrock call carries the tool result back to the model.
    last_message = seen[1]["messages"][-1]
    assert last_message["content"][0]["toolResult"]["toolUseId"] == "t1"
    assert "Tuesday, October 06, 2026" in seen[0]["system"][0]["text"]


def test_gives_up_after_too_many_tool_rounds():
    converse, _ = scripted_converse(*([TOOL_USE] * 10))
    events = collect(run_turn(converse, "model", FakeToolbox(), [], "loop forever"))
    assert events[-1]["type"] == "answer"
    assert events[-1]["text"].startswith("Sorry")


def test_build_messages_skips_empty_turns():
    messages = build_messages([{"role": "user", "text": "hi"}, {"role": "assistant", "text": ""}], "next")
    assert [m["content"][0]["text"] for m in messages] == ["hi", "next"]
