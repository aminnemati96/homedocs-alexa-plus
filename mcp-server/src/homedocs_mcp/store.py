"""Household documents, their key dates, and the search interface.

`DocumentStore` holds the documents and answers date questions. Search is
pluggable: `KeywordSearcher` works offline (tests, quick checks) and
`homedocs_mcp.vector_search.VectorSearcher` uses Bedrock embeddings + Qdrant.
"""

from __future__ import annotations

import json
import re
from datetime import date, timedelta
from pathlib import Path
from typing import Protocol

from pydantic import BaseModel

_WORD = re.compile(r"[a-z0-9]+")
_STOPWORDS = {
    "a", "an", "and", "are", "at", "be", "by", "do", "does", "for", "how", "i",
    "in", "is", "it", "my", "of", "on", "or", "the", "to", "what", "when", "will",
    "with", "still", "under",
}


class KeyDate(BaseModel):
    label: str
    date: date


class Document(BaseModel):
    id: str
    title: str
    category: str
    provider: str
    key_dates: list[KeyDate]
    text: str


class SearchHit(BaseModel):
    document_id: str
    title: str
    score: float
    passage: str


class UpcomingDate(BaseModel):
    document_id: str
    title: str
    label: str
    date: date
    days_away: int


class Searcher(Protocol):
    def search(self, query: str, top_k: int) -> list[SearchHit]: ...


def load_documents(path: Path) -> list[Document]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return [Document.model_validate(item) for item in raw]


class DocumentStore:
    def __init__(self, documents: list[Document]):
        self._docs = {d.id: d for d in documents}

    @classmethod
    def from_json(cls, path: Path) -> "DocumentStore":
        return cls(load_documents(path))

    def list_all(self) -> list[Document]:
        return list(self._docs.values())

    def get(self, document_id: str) -> Document | None:
        return self._docs.get(document_id)

    def upcoming(self, days_ahead: int, today: date | None = None) -> list[UpcomingDate]:
        today = today or date.today()
        horizon = today + timedelta(days=days_ahead)
        result = [
            UpcomingDate(
                document_id=doc.id,
                title=doc.title,
                label=kd.label,
                date=kd.date,
                days_away=(kd.date - today).days,
            )
            for doc in self._docs.values()
            for kd in doc.key_dates
            if today <= kd.date <= horizon
        ]
        result.sort(key=lambda u: u.date)
        return result


def _tokens(text: str) -> set[str]:
    return {t for t in _WORD.findall(text.lower()) if t not in _STOPWORDS}


class KeywordSearcher:
    """Ranks whole documents by word overlap with the query. No network needed."""

    def __init__(self, documents: list[Document]):
        self._docs = documents

    def search(self, query: str, top_k: int = 3) -> list[SearchHit]:
        query_tokens = _tokens(query)
        if not query_tokens:
            return []
        hits = []
        for doc in self._docs:
            doc_tokens = _tokens(f"{doc.title} {doc.category} {doc.text}")
            overlap = len(query_tokens & doc_tokens)
            if overlap:
                hits.append(
                    SearchHit(
                        document_id=doc.id,
                        title=doc.title,
                        score=overlap / len(query_tokens),
                        passage=doc.text,
                    )
                )
        hits.sort(key=lambda h: h.score, reverse=True)
        return hits[:top_k]
