"""Household documents, their key dates, and the search interface.

`DocumentStore` holds the documents and answers date questions. Search is
pluggable: `KeywordSearcher` works offline (tests, quick checks) and
`homedocs_mcp.vector_search.VectorSearcher` uses Bedrock embeddings + Qdrant.
"""

from __future__ import annotations

import json
import re
import uuid
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

    def index(self, doc: Document) -> int: ...

    def delete(self, doc: Document) -> None: ...


def load_documents(path: Path) -> list[Document]:
    if not path.exists():
        return []
    raw = json.loads(path.read_text(encoding="utf-8"))
    return [Document.model_validate(item) for item in raw]


def new_document_id(title: str) -> str:
    slug = "-".join(_WORD.findall(title.lower()))[:40].strip("-") or "document"
    return f"{slug}-{uuid.uuid4().hex[:6]}"


class DocumentStore:
    """Sample documents (read-only) plus documents the user added.

    Added documents are saved to `user_path` so they survive restarts.
    """

    def __init__(self, documents: list[Document], user_path: Path | None = None):
        self._docs = {d.id: d for d in documents}
        self._user_path = user_path
        self._user_ids: list[str] = []
        if user_path is not None:
            for doc in load_documents(user_path):
                self._docs[doc.id] = doc
                self._user_ids.append(doc.id)

    @classmethod
    def from_json(cls, path: Path, user_path: Path | None = None) -> "DocumentStore":
        return cls(load_documents(path), user_path)

    def list_all(self) -> list[Document]:
        return list(self._docs.values())

    def get(self, document_id: str) -> Document | None:
        return self._docs.get(document_id)

    def add(self, doc: Document) -> None:
        if doc.id in self._docs:
            raise ValueError(f"A document with id '{doc.id}' already exists")
        self._docs[doc.id] = doc
        self._user_ids.append(doc.id)
        self._save_user_docs()

    def put(self, doc: Document) -> None:
        """Insert or replace (used to restore sample documents)."""
        self._docs[doc.id] = doc
        if doc.id in self._user_ids:
            self._save_user_docs()

    def delete(self, document_id: str) -> Document | None:
        """Remove a document. Deleting a sample only lasts until the next restart."""
        doc = self._docs.pop(document_id, None)
        if document_id in self._user_ids:
            self._user_ids.remove(document_id)
            self._save_user_docs()
        return doc

    def _save_user_docs(self) -> None:
        if self._user_path is None:
            return
        user_docs = [self._docs[i].model_dump(mode="json") for i in self._user_ids]
        self._user_path.parent.mkdir(parents=True, exist_ok=True)
        self._user_path.write_text(json.dumps(user_docs, indent=2), encoding="utf-8")

    def upcoming(self, days_ahead: int, today: date | None = None) -> list[UpcomingDate]:
        return upcoming_dates(self.list_all(), days_ahead, today)


class Store(Protocol):
    """What the MCP tools need; implemented by DocumentStore (local JSON files)
    and homedocs_mcp.cloud.DynamoDocumentStore (DynamoDB)."""

    def list_all(self) -> list[Document]: ...

    def get(self, document_id: str) -> Document | None: ...

    def add(self, doc: Document) -> None: ...

    def put(self, doc: Document) -> None: ...

    def delete(self, document_id: str) -> Document | None: ...

    def upcoming(self, days_ahead: int, today: date | None = None) -> list[UpcomingDate]: ...


def upcoming_dates(docs: list[Document], days_ahead: int, today: date | None = None) -> list[UpcomingDate]:
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
        for doc in docs
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
        self._docs = list(documents)

    def index(self, doc: Document) -> int:
        self.delete(doc)
        self._docs.append(doc)
        return 1

    def delete(self, doc: Document) -> None:
        self._docs = [d for d in self._docs if d.id != doc.id]

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
