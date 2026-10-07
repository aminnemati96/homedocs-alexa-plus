"""Settings from environment variables, and the factories that use them."""

from __future__ import annotations

import os
from pathlib import Path

from homedocs_mcp.store import DocumentStore, KeywordSearcher, Searcher

_DATA_DIR = Path(__file__).resolve().parents[2] / "data"

DATA_PATH = Path(os.environ.get("HOMEDOCS_DATA", _DATA_DIR / "sample_documents.json"))
USER_DATA_PATH = Path(os.environ.get("HOMEDOCS_USER_DATA", _DATA_DIR / "user_documents.json"))
SEARCH_MODE = os.environ.get("HOMEDOCS_SEARCH", "vector")  # "vector" or "keyword"
QDRANT_URL = os.environ.get("QDRANT_URL", "http://localhost:6333")
COLLECTION = os.environ.get("HOMEDOCS_COLLECTION", "homedocs")
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
HOST = os.environ.get("HOMEDOCS_HOST", "127.0.0.1")
PORT = int(os.environ.get("HOMEDOCS_PORT", "8000"))


def make_store() -> DocumentStore:
    return DocumentStore.from_json(DATA_PATH, USER_DATA_PATH)


def make_vector_searcher():
    # Imported here so keyword mode and the tests don't need AWS or Qdrant.
    from qdrant_client import QdrantClient

    from homedocs_mcp.embeddings import TitanEmbedder
    from homedocs_mcp.vector_search import VectorSearcher

    return VectorSearcher(
        QdrantClient(url=QDRANT_URL), TitanEmbedder(region=AWS_REGION), COLLECTION
    )


def make_searcher(store: DocumentStore) -> Searcher:
    if SEARCH_MODE == "keyword":
        return KeywordSearcher(store.list_all())
    if SEARCH_MODE == "vector":
        searcher = make_vector_searcher()
        searcher.ensure_collection()
        return searcher
    raise ValueError(f"HOMEDOCS_SEARCH must be 'vector' or 'keyword', got '{SEARCH_MODE}'")
