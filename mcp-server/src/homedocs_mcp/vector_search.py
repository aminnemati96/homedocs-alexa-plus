"""Passage-level semantic search: documents are split into passages, embedded
with Bedrock, and stored in Qdrant."""

from __future__ import annotations

import re
import uuid
from typing import Protocol

from qdrant_client import QdrantClient, models

from homedocs_mcp.store import Document, SearchHit

_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")
_ID_NAMESPACE = uuid.UUID("6f1d3c2e-9a4b-4f7e-8c55-2b0e1d7a9c11")


class Embedder(Protocol):
    dimensions: int

    def embed(self, text: str) -> list[float]: ...


def split_passages(text: str, sentences_per_passage: int = 3, overlap: int = 1) -> list[str]:
    """Group sentences into short overlapping passages.

    Household documents are short, so a few sentences per passage keeps each
    answer specific without losing the surrounding context.
    """
    sentences = [s.strip() for s in _SENTENCE_END.split(text) if s.strip()]
    if len(sentences) <= sentences_per_passage:
        return [" ".join(sentences)] if sentences else []
    step = sentences_per_passage - overlap
    passages = []
    for start in range(0, len(sentences), step):
        passages.append(" ".join(sentences[start : start + sentences_per_passage]))
        if start + sentences_per_passage >= len(sentences):
            break
    return passages


class VectorSearcher:
    def __init__(self, qdrant: QdrantClient, embedder: Embedder, collection: str = "homedocs"):
        self._qdrant = qdrant
        self._embedder = embedder
        self._collection = collection

    def ensure_collection(self) -> None:
        if not self._qdrant.collection_exists(self._collection):
            self._qdrant.create_collection(
                collection_name=self._collection,
                vectors_config=models.VectorParams(
                    size=self._embedder.dimensions, distance=models.Distance.COSINE
                ),
            )

    def index(self, doc: Document) -> int:
        """Replace all passages of one document. Returns the passage count."""
        self._qdrant.delete(
            collection_name=self._collection,
            points_selector=models.FilterSelector(
                filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="document_id", match=models.MatchValue(value=doc.id)
                        )
                    ]
                )
            ),
        )
        points = [
            models.PointStruct(
                id=str(uuid.uuid5(_ID_NAMESPACE, f"{doc.id}:{i}")),
                # The title gives each passage context ("Dishwasher warranty: ...").
                vector=self._embedder.embed(f"{doc.title}: {passage}"),
                payload={"document_id": doc.id, "title": doc.title, "passage": passage},
            )
            for i, passage in enumerate(split_passages(doc.text))
        ]
        if points:
            self._qdrant.upsert(collection_name=self._collection, points=points)
        return len(points)

    def search(self, query: str, top_k: int = 3) -> list[SearchHit]:
        result = self._qdrant.query_points(
            collection_name=self._collection,
            query=self._embedder.embed(query),
            limit=top_k,
            with_payload=True,
        )
        return [
            SearchHit(
                document_id=p.payload["document_id"],
                title=p.payload["title"],
                score=p.score,
                passage=p.payload["passage"],
            )
            for p in result.points
        ]
