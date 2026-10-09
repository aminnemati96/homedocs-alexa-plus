"""End-to-end scenario checks against a running MCP server and real Bedrock.

Unlike the unit tests, these run real conversations and check what actually
happened (which tools ran, what is stored) instead of trusting the model's words.

    uv run python evals/scenarios.py

Uses the same settings as the agent (MCP_URL, Cognito variables, BEDROCK_MODEL_ID).
Writes test documents and removes them again at the end.
"""

from __future__ import annotations

import asyncio
import json
import re
import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from homedocs_agent import aws, config
from homedocs_agent.agent import run_turn
from homedocs_agent.connection import open_mcp
from homedocs_agent.extract import extract

TODAY = date(2026, 10, 9)
SAMPLES = {"passport", "internet-bill-sep-2026", "apartment-lease", "dishwasher-warranty", "auto-insurance-2026"}
RECEIPT = Path(__file__).resolve().parents[2] / "samples" / "laptop-receipt.png"


@dataclass
class Turn:
    answer: str = ""
    tools: list[tuple[str, dict]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


async def ask(text: str, history: list[dict] | None = None) -> Turn:
    turn = Turn()
    async with open_mcp() as toolbox:
        async for e in run_turn(aws.bedrock().converse_stream, config.MODEL_ID, toolbox, history or [], text, today=TODAY):
            if e["type"] == "tool_call":
                turn.tools.append((e["name"], e["input"]))
            elif e["type"] == "tool_result" and e["is_error"]:
                turn.errors.append(json.dumps(e["output"])[:200])
            elif e["type"] == "answer":
                turn.answer = e["text"]
    return turn


async def documents() -> dict[str, dict]:
    async with open_mcp() as toolbox:
        listed, _ = await toolbox.call("list_documents", {})
    return {d["id"]: d for d in listed.get("result", [])}


async def call(name: str, args: dict) -> tuple[dict, bool]:
    async with open_mcp() as toolbox:
        return await toolbox.call(name, args)


results: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok, detail))
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else f"  ->  {detail}"))


def names(turn: Turn) -> list[str]:
    return [n for n, _ in turn.tools]


async def conversation_checks() -> None:
    # Notifications and follow-ups
    t1 = await ask("What are my notifications?")
    check("notifications: uses list_upcoming_dates", "list_upcoming_dates" in names(t1), str(t1.tools))
    check("notifications: mentions the internet bill", "internet" in t1.answer.lower(), t1.answer)
    check("notifications: no dishwasher (22 days away)", "dishwasher" not in t1.answer.lower(), t1.answer)
    history = [{"role": "user", "text": "What are my notifications?"}, {"role": "assistant", "text": t1.answer}]
    t2 = await ask("Do I have any more notifications?", history)
    check("follow-up: says there are no other notifications", re.search(r"\bno (other|more)\b", t2.answer.lower()) is not None, t2.answer)
    check("follow-up: invents no home insurance", "home insurance" not in t2.answer.lower(), t2.answer)

    t2b = await ask("Do I have anything else coming up?", history)
    answer = t2b.answer.lower()
    check("coming up: lists all three later dates (none dropped)",
          all(k in answer for k in ("dishwasher", "car insurance", "promotional")), t2b.answer)

    t3 = await ask("hello")
    check("greeting: answers without errors", bool(t3.answer) and not t3.errors, f"{t3.answer} {t3.errors}")

    # Questions with known answers
    facts = [
        ("Can I have a cat in my apartment?", ["300"]),
        ("When does my car insurance renew?", ["november 14"]),
        ("How much is my rent?", ["1,950"]),
        ("Is heat included in my rent?", ["heat"]),
        ("When does my passport expire?", ["february 20"]),
        ("What's my wifi network name?", ["unit304-home"]),
        ("What's my collision deductible?", ["500"]),
    ]
    for question, needles in facts:
        t = await ask(question)
        ok = all(n in t.answer.lower().replace("$", "") or n in t.answer.lower() for n in needles)
        check(f"fact: {question}", ok, t.answer)

    t = await ask("How much is my gym membership?")
    check("unknown: admits it doesn't know", re.search(r"(don't|do not|couldn't|could not|no )", t.answer.lower()) is not None, t.answer)
    check("unknown: invents no amount", re.search(r"\$\d", t.answer) is None, t.answer)

    # Not a delete request, even though it says "remove"
    before = set(await documents())
    t = await ask("Can my landlord remove the pet deposit?")
    after = set(await documents())
    check("'remove' in a question deletes nothing", before == after and "delete_document" not in names(t), f"{names(t)} {before - after}")

    # Save, recall, delete by voice
    t = await ask("Remember that my gym membership renews November 1st.")
    docs = await documents()
    gym = [d for d in docs.values() if "gym" in d["title"].lower()]
    check("save: save_document called and stored", "save_document" in names(t) and len(gym) == 1, f"{names(t)} {list(docs)}")
    if gym:
        dates = [k["date"] for k in gym[0]["key_dates"]]
        check("save: stores 2026-11-01", "2026-11-01" in dates, str(dates))
    t = await ask("When does my gym membership renew?")
    check("recall: finds the saved note", "november 1" in t.answer.lower(), t.answer)
    t = await ask("Forget my gym membership.")
    docs = await documents()
    check("delete: delete_document called and removed", "delete_document" in names(t) and not any("gym" in d["title"].lower() for d in docs.values()), f"{names(t)} {[d['title'] for d in docs.values()]}")
    t = await ask("Delete my lottery ticket.")
    check("delete of something missing: removes nothing", set(await documents()) == SAMPLES, str(list(await documents())))
    check("delete of something missing: doesn't claim success", re.search(r"\b(deleted|removed)\b", t.answer.lower()) is None or "no " in t.answer.lower() or "couldn't" in t.answer.lower(), t.answer)


async def upload_checks() -> None:
    fields = extract(aws.bedrock().converse, config.MODEL_ID, "image/png", RECEIPT.read_bytes(), TODAY)
    text = fields["text"].lower()
    check("upload: title names the laptop", "lumora" in fields["title"].lower() or "laptop" in fields["title"].lower(), fields["title"])
    check("upload: 'one claim per year', not '$1'", "$1 claim" not in text and ("one claim" in text or "1 claim" in text), fields["text"])
    dates = {k["date"] for k in fields["key_dates"]}
    check("upload: warranty dates extracted", {"2026-11-20", "2027-11-20"} <= dates, str(dates))
    check("upload: no real brand names", not re.search(r"asus|zenbook|visa|mic mac", text), fields["text"])
    saved, err = await call("save_document", fields)
    check("upload: saved", not err and "id" in saved, str(saved)[:200])
    t = await ask("What happens if I spill coffee on my laptop?")
    check("upload: coffee answer uses the receipt", "99" in t.answer and "claim" in t.answer.lower(), t.answer)
    check("upload: coffee answer has no '$1'", "$1 " not in t.answer, t.answer)


async def mcp_checks() -> None:
    up, _ = await call("list_upcoming_dates", {"days_ahead": 14, "today": "2026-10-09"})
    check("mcp: 14-day window from Oct 9 is only the internet bill", [u["document_id"] for u in up["result"]] == ["internet-bill-sep-2026"], str(up))
    up, _ = await call("list_upcoming_dates", {"days_ahead": 1, "today": "2026-10-15"})
    check("mcp: due today has days_away 0", up["result"] and up["result"][0]["days_away"] == 0, str(up))
    hits, _ = await call("search_documents", {"query": "rent", "top_k": 50})
    check("mcp: top_k is capped at 10", len(hits["result"]) <= 10, str(len(hits["result"])))
    _, err = await call("get_document", {"document_id": "does-not-exist"})
    check("mcp: get_document on a missing id is an error", err)
    _, err = await call("delete_document", {"document_id": "does-not-exist"})
    check("mcp: delete_document on a missing id is an error", err)
    bad, err = await call("save_document", {"title": "Bad", "category": "other", "text": "x", "key_dates": [{"label": "x", "date": "not-a-date"}]})
    check("mcp: save with a bad date is rejected", err, str(bad)[:200])
    check("mcp: rejected save stored nothing", set(await documents()) == SAMPLES, str(list(await documents())))


async def cleanup() -> None:
    for doc_id in set(await documents()) - SAMPLES:
        await call("delete_document", {"document_id": doc_id})
    check("cleanup: only the samples remain", set(await documents()) == SAMPLES, str(list(await documents())))


async def main() -> int:
    try:
        await mcp_checks()
        await conversation_checks()
        await upload_checks()
    finally:
        await cleanup()
    failed = [r for r in results if not r[1]]
    print(f"\n{len(results) - len(failed)} passed, {len(failed)} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
