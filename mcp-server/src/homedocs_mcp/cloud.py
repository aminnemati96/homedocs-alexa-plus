"""AWS-native storage for the deployed server: documents in DynamoDB,
passage embeddings in Amazon S3 Vectors.

Nothing is cached in memory: the server may run as several AgentCore sessions
at once, so every call reads the current data. At household scale (tens of
documents) a full table scan is a few milliseconds.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from homedocs_mcp.store import Document, SearchHit, UpcomingDate, upcoming_dates
from homedocs_mcp.vector_search import Embedder, split_passages


class DynamoDocumentStore:
    """Table with partition key `id` (string); the document is stored as JSON in `body`."""

    def __init__(self, client: Any, table: str):
        self._client = client
        self._table = table

    def list_all(self) -> list[Document]:
        paginator = self._client.get_paginator("scan")
        return [
            Document.model_validate_json(item["body"]["S"])
            for item in paginator.paginate(TableName=self._table).search("Items[]")
        ]

    def get(self, document_id: str) -> Document | None:
        response = self._client.get_item(TableName=self._table, Key={"id": {"S": document_id}})
        item = response.get("Item")
        return Document.model_validate_json(item["body"]["S"]) if item else None

    def add(self, doc: Document) -> None:
        try:
            self._client.put_item(
                TableName=self._table,
                Item={"id": {"S": doc.id}, "body": {"S": doc.model_dump_json()}},
                ConditionExpression="attribute_not_exists(id)",
            )
        except self._client.exceptions.ConditionalCheckFailedException as e:
            raise ValueError(f"A document with id '{doc.id}' already exists") from e

    def put(self, doc: Document) -> None:
        """Insert or replace; used by ingest to (re)seed the sample documents."""
        self._client.put_item(
            TableName=self._table,
            Item={"id": {"S": doc.id}, "body": {"S": doc.model_dump_json()}},
        )

    def delete(self, document_id: str) -> Document | None:
        response = self._client.delete_item(
            TableName=self._table, Key={"id": {"S": document_id}}, ReturnValues="ALL_OLD"
        )
        old = response.get("Attributes")
        return Document.model_validate_json(old["body"]["S"]) if old else None

    def upcoming(self, days_ahead: int, today: date | None = None) -> list[UpcomingDate]:
        return upcoming_dates(self.list_all(), days_ahead, today)


class S3VectorsSearcher:
    """Same passage scheme as the Qdrant searcher, stored in an S3 vector index.

    The index must use cosine distance and the embedder's dimension, with
    `title` and `passage` as non-filterable metadata (see infra/).
    """

    def __init__(self, client: Any, embedder: Embedder, bucket: str, index: str):
        self._client = client
        self._embedder = embedder
        self._bucket = bucket
        self._index = index

    def index(self, doc: Document) -> int:
        # Keys are deterministic, so re-indexing a document overwrites its passages.
        vectors = [
            {
                "key": f"{doc.id}#{i}",
                "data": {"float32": self._embedder.embed(f"{doc.title}: {passage}")},
                "metadata": {"document_id": doc.id, "title": doc.title, "passage": passage},
            }
            for i, passage in enumerate(split_passages(doc.text))
        ]
        if vectors:
            self._client.put_vectors(vectorBucketName=self._bucket, indexName=self._index, vectors=vectors)
        return len(vectors)

    def delete(self, doc: Document) -> None:
        # Keys are "<id>#<n>", one per passage, so the text tells us which exist.
        keys = [f"{doc.id}#{i}" for i in range(len(split_passages(doc.text)))]
        if keys:
            self._client.delete_vectors(vectorBucketName=self._bucket, indexName=self._index, keys=keys)

    def search(self, query: str, top_k: int = 3) -> list[SearchHit]:
        response = self._client.query_vectors(
            vectorBucketName=self._bucket,
            indexName=self._index,
            queryVector={"float32": self._embedder.embed(query)},
            topK=top_k,
            returnMetadata=True,
            returnDistance=True,
        )
        return [
            SearchHit(
                document_id=v["metadata"]["document_id"],
                title=v["metadata"]["title"],
                # Cosine distance is 1 - similarity; report similarity like Qdrant does.
                score=1.0 - v["distance"],
                passage=v["metadata"]["passage"],
            )
            for v in response["vectors"]
        ]
