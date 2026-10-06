"""Settings from environment variables, and the factories that use them."""

from __future__ import annotations

import os
from pathlib import Path

from homedocs_mcp.store import KeywordSearcher, Searcher, load_documents

DEFAULT_DATA = Path(__file__).resolve().parents[2] / "data" / "sample_documents.json"

DATA_PATH = Path(os.environ.get("HOMEDOCS_DATA", DEFAULT_DATA))
SEARCH_MODE = os.environ.get("HOMEDOCS_SEARCH", "vector")  # "vector" or "keyword"
QDRANT_URL = os.environ.get("QDRANT_URL", "http://localhost:6333")
COLLECTION = os.environ.get("HOMEDOCS_COLLECTION", "homedocs")
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
HOST = os.environ.get("HOMEDOCS_HOST", "127.0.0.1")
PORT = int(os.environ.get("HOMEDOCS_PORT", "8000"))


def make_vector_searcher():
    # Imported here so keyword mode and the tests don't need AWS or Qdrant.
    from qdrant_client import QdrantClient

    from homedocs_mcp.embeddings import TitanEmbedder
    from homedocs_mcp.vector_search import VectorSearcher

    return VectorSearcher(
        QdrantClient(url=QDRANT_URL), TitanEmbedder(region=AWS_REGION), COLLECTION
    )


def make_searcher() -> Searcher:
    if SEARCH_MODE == "keyword":
        return KeywordSearcher(load_documents(DATA_PATH))
    if SEARCH_MODE == "vector":
        return make_vector_searcher()
    raise ValueError(f"HOMEDOCS_SEARCH must be 'vector' or 'keyword', got '{SEARCH_MODE}'")
