"""Document store for household paperwork.

This first version loads documents from a JSON file and ranks them with simple
keyword overlap. The next step replaces `search` with vector search
(Bedrock embeddings + Qdrant) without changing the tool signatures in server.py.
"""

from __future__ import annotations

import json
import re
from datetime import date, timedelta
from pathlib import Path

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


def _tokens(text: str) -> set[str]:
    return {t for t in _WORD.findall(text.lower()) if t not in _STOPWORDS}


class DocumentStore:
    def __init__(self, documents: list[Document]):
        self._docs = {d.id: d for d in documents}

    @classmethod
    def from_json(cls, path: Path) -> "DocumentStore":
        raw = json.loads(path.read_text(encoding="utf-8"))
        return cls([Document.model_validate(item) for item in raw])

    def list_all(self) -> list[Document]:
        return list(self._docs.values())

    def get(self, document_id: str) -> Document | None:
        return self._docs.get(document_id)

    def search(self, query: str, top_k: int = 3) -> list[SearchHit]:
        query_tokens = _tokens(query)
        if not query_tokens:
            return []
        hits = []
        for doc in self._docs.values():
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
