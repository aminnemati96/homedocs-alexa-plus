from datetime import date
from pathlib import Path

from homedocs_mcp.store import (
    Document,
    DocumentStore,
    KeyDate,
    KeywordSearcher,
    load_documents,
    new_document_id,
)

DATA = Path(__file__).resolve().parents[1] / "data" / "sample_documents.json"
# Sample dates are offsets from "today"; pin it so the expected dates are fixed.
SAMPLE_DAY = date(2026, 10, 9)


def make_searcher() -> KeywordSearcher:
    return KeywordSearcher(load_documents(DATA, SAMPLE_DAY))


def test_search_finds_insurance_renewal():
    hits = make_searcher().search("when does my car insurance renew")
    assert hits[0].document_id == "car-insurance"


def test_search_finds_dishwasher_warranty():
    hits = make_searcher().search("is the dishwasher still under warranty")
    assert hits[0].document_id == "dishwasher-warranty"


def test_search_with_only_stopwords_returns_nothing():
    assert make_searcher().search("what is it") == []


def test_upcoming_is_sorted_and_bounded():
    upcoming = DocumentStore.from_json(DATA, today=SAMPLE_DAY).upcoming(days_ahead=30, today=date(2026, 10, 6))
    assert [u.document_id for u in upcoming] == [
        "internet-bill",
        "dishwasher-warranty",
    ]
    assert upcoming[0].days_away == 9


def test_added_documents_persist_across_restarts(tmp_path):
    user_file = tmp_path / "user_documents.json"
    doc = Document(
        id=new_document_id("Car registration"),
        title="Car registration",
        category="vehicle",
        provider="",
        key_dates=[KeyDate(label="Registration renews", date=date(2027, 5, 3))],
        text="Registration for the Corvane sedan renews May 3, 2027.",
    )
    DocumentStore.from_json(DATA, user_file, SAMPLE_DAY).add(doc)

    reopened = DocumentStore.from_json(DATA, user_file, SAMPLE_DAY)
    assert reopened.get(doc.id) == doc
    assert len(reopened.list_all()) == len(load_documents(DATA, SAMPLE_DAY)) + 1


def test_new_document_id_is_a_unique_slug():
    first = new_document_id("Home Insurance (2026)!")
    assert first.startswith("home-insurance-2026-")
    assert first != new_document_id("Home Insurance (2026)!")


def test_delete_and_restore(tmp_path):
    user_file = tmp_path / "user_documents.json"
    store = DocumentStore.from_json(DATA, user_file, SAMPLE_DAY)
    note = Document(id="note-1", title="Note", category="other", provider="", key_dates=[], text="Hi.")
    store.add(note)
    assert store.delete("note-1") == note
    assert store.get("note-1") is None
    assert DocumentStore.from_json(DATA, user_file, SAMPLE_DAY).get("note-1") is None
    assert store.delete("missing") is None


def test_upcoming_uses_the_given_local_date():
    store = DocumentStore.from_json(DATA, today=SAMPLE_DAY)
    # Oct 15 is "today" for the user, even if the server's UTC date is already Oct 16.
    upcoming = store.upcoming(days_ahead=1, today=date(2026, 10, 15))
    assert [(u.document_id, u.days_away) for u in upcoming] == [("internet-bill", 0)]


def test_skill_file_follows_the_agent_skills_format():
    from homedocs_mcp.config import SKILL_PATH

    text = SKILL_PATH.read_text(encoding="utf-8")
    frontmatter = text.split("---")[1]
    assert "name: homedocs-paperwork" in frontmatter
    assert SKILL_PATH.parent.name == "homedocs-paperwork"  # name must match the folder
    description = next(line for line in frontmatter.splitlines() if line.startswith("description:"))
    assert len(description) - len("description: ") <= 1024



def test_sample_dates_roll_with_today():
    from homedocs_mcp.store import resolve_relative_dates

    later = load_documents(DATA, date(2026, 11, 15))
    bill = next(d for d in later if d.id == "internet-bill")
    assert bill.key_dates[0].date == date(2026, 11, 21)  # always 6 days out
    assert "November 21, 2026" in bill.text
    assert bill.title == "Internet bill, October 2026"
    assert resolve_relative_dates("{iso:-1}", date(2026, 1, 1)) == "2025-12-31"
