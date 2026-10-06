from datetime import date
from pathlib import Path

from homedocs_mcp.store import DocumentStore

DATA = Path(__file__).resolve().parents[1] / "data" / "sample_documents.json"


def make_store() -> DocumentStore:
    return DocumentStore.from_json(DATA)


def test_search_finds_insurance_renewal():
    hits = make_store().search("when does my car insurance renew")
    assert hits[0].document_id == "auto-insurance-2026"


def test_search_finds_dishwasher_warranty():
    hits = make_store().search("is the dishwasher still under warranty")
    assert hits[0].document_id == "dishwasher-warranty"


def test_search_with_only_stopwords_returns_nothing():
    assert make_store().search("what is it") == []


def test_upcoming_is_sorted_and_bounded():
    upcoming = make_store().upcoming(days_ahead=30, today=date(2026, 10, 6))
    assert [u.document_id for u in upcoming] == [
        "internet-bill-sep-2026",
        "dishwasher-warranty",
    ]
    assert upcoming[0].days_away == 9
