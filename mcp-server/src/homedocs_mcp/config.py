"""Settings from environment variables, and the factories that use them.

Local development: HOMEDOCS_STORE=file, HOMEDOCS_SEARCH=vector (Qdrant).
Deployed on AWS:   HOMEDOCS_STORE=dynamodb, HOMEDOCS_SEARCH=s3vectors.
"""

from __future__ import annotations

import os
from pathlib import Path

from homedocs_mcp.store import DocumentStore, KeywordSearcher, Searcher, Store

_PROJECT_DIR = Path(__file__).resolve().parents[2]
_DATA_DIR = _PROJECT_DIR / "data"
SKILL_PATH = _PROJECT_DIR / "skills" / "homedocs-paperwork" / "SKILL.md"

DATA_PATH = Path(os.environ.get("HOMEDOCS_DATA", _DATA_DIR / "sample_documents.json"))
USER_DATA_PATH = Path(os.environ.get("HOMEDOCS_USER_DATA", _DATA_DIR / "user_documents.json"))
STORE_MODE = os.environ.get("HOMEDOCS_STORE", "file")  # "file" or "dynamodb"
SEARCH_MODE = os.environ.get("HOMEDOCS_SEARCH", "vector")  # "vector", "s3vectors" or "keyword"
QDRANT_URL = os.environ.get("QDRANT_URL", "http://localhost:6333")
COLLECTION = os.environ.get("HOMEDOCS_COLLECTION", "homedocs")
DOCUMENTS_TABLE = os.environ.get("HOMEDOCS_TABLE", "homedocs-documents")
VECTOR_BUCKET = os.environ.get("HOMEDOCS_VECTOR_BUCKET", "")
VECTOR_INDEX = os.environ.get("HOMEDOCS_VECTOR_INDEX", "passages")
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
# "true" registers admin_reset_demo (used by the nightly reset on the public demo).
ADMIN_TOOLS = os.environ.get("HOMEDOCS_ADMIN_TOOLS", "").lower() == "true"
HOST = os.environ.get("HOMEDOCS_HOST", "127.0.0.1")
PORT = int(os.environ.get("HOMEDOCS_PORT", "8000"))


def make_store() -> Store:
    if STORE_MODE == "file":
        return DocumentStore.from_json(DATA_PATH, USER_DATA_PATH)
    if STORE_MODE == "dynamodb":
        import boto3

        from homedocs_mcp.cloud import DynamoDocumentStore

        return DynamoDocumentStore(boto3.client("dynamodb", region_name=AWS_REGION), DOCUMENTS_TABLE)
    raise ValueError(f"HOMEDOCS_STORE must be 'file' or 'dynamodb', got '{STORE_MODE}'")


def make_vector_searcher():
    # Imported here so keyword mode and the tests don't need AWS or Qdrant.
    from qdrant_client import QdrantClient

    from homedocs_mcp.embeddings import TitanEmbedder
    from homedocs_mcp.vector_search import VectorSearcher

    return VectorSearcher(
        QdrantClient(url=QDRANT_URL), TitanEmbedder(region=AWS_REGION), COLLECTION
    )


def make_s3vectors_searcher():
    import boto3

    from homedocs_mcp.cloud import S3VectorsSearcher
    from homedocs_mcp.embeddings import TitanEmbedder

    if not VECTOR_BUCKET:
        raise ValueError("HOMEDOCS_VECTOR_BUCKET must be set when HOMEDOCS_SEARCH=s3vectors")
    return S3VectorsSearcher(
        boto3.client("s3vectors", region_name=AWS_REGION),
        TitanEmbedder(region=AWS_REGION),
        VECTOR_BUCKET,
        VECTOR_INDEX,
    )


def make_searcher(store: Store) -> Searcher:
    if SEARCH_MODE == "keyword":
        return KeywordSearcher(store.list_all())
    if SEARCH_MODE == "vector":
        searcher = make_vector_searcher()
        searcher.ensure_collection()
        return searcher
    if SEARCH_MODE == "s3vectors":
        return make_s3vectors_searcher()
    raise ValueError(
        f"HOMEDOCS_SEARCH must be 'vector', 's3vectors' or 'keyword', got '{SEARCH_MODE}'"
    )
