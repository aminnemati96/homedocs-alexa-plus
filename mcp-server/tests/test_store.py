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


def make_searcher() -> KeywordSearcher:
    return KeywordSearcher(load_documents(DATA))


def test_search_finds_insurance_renewal():
    hits = make_searcher().search("when does my car insurance renew")
    assert hits[0].document_id == "auto-insurance-2026"


def test_search_finds_dishwasher_warranty():
    hits = make_searcher().search("is the dishwasher still under warranty")
    assert hits[0].document_id == "dishwasher-warranty"


def test_search_with_only_stopwords_returns_nothing():
    assert make_searcher().search("what is it") == []


def test_upcoming_is_sorted_and_bounded():
    upcoming = DocumentStore.from_json(DATA).upcoming(days_ahead=30, today=date(2026, 10, 6))
    assert [u.document_id for u in upcoming] == [
        "internet-bill-sep-2026",
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
        text="Registration for the Honda Civic renews May 3, 2027.",
    )
    DocumentStore.from_json(DATA, user_file).add(doc)

    reopened = DocumentStore.from_json(DATA, user_file)
    assert reopened.get(doc.id) == doc
    assert len(reopened.list_all()) == len(load_documents(DATA)) + 1


def test_new_document_id_is_a_unique_slug():
    first = new_document_id("Home Insurance (2026)!")
    assert first.startswith("home-insurance-2026-")
    assert first != new_document_id("Home Insurance (2026)!")


def test_delete_and_restore(tmp_path):
    user_file = tmp_path / "user_documents.json"
    store = DocumentStore.from_json(DATA, user_file)
    note = Document(id="note-1", title="Note", category="other", provider="", key_dates=[], text="Hi.")
    store.add(note)
    assert store.delete("note-1") == note
    assert store.get("note-1") is None
    assert DocumentStore.from_json(DATA, user_file).get("note-1") is None
    assert store.delete("missing") is None


def test_upcoming_uses_the_given_local_date():
    store = DocumentStore.from_json(DATA)
    # Oct 15 is "today" for the user, even if the server's UTC date is already Oct 16.
    upcoming = store.upcoming(days_ahead=1, today=date(2026, 10, 15))
    assert [(u.document_id, u.days_away) for u in upcoming] == [("internet-bill-sep-2026", 0)]
