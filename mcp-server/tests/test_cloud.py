"""DynamoDB and S3 Vectors adapters against small in-memory fakes of the boto3 clients."""

from datetime import date

import pytest

from homedocs_mcp.cloud import DynamoDocumentStore, S3VectorsSearcher
from homedocs_mcp.store import Document, KeyDate

DOC = Document(
    id="hydro-bill-abc123",
    title="Hydro bill",
    category="bill",
    provider="Brightwater Power",
    key_dates=[KeyDate(label="Payment due", date=date(2026, 10, 28))],
    text="Amount due is $112.40. Due October 28, 2026. Late charge is 1.5% per month.",
)


class FakeDynamo:
    class exceptions:
        class ConditionalCheckFailedException(Exception):
            pass

    def __init__(self):
        self.items = {}

    def put_item(self, TableName, Item, ConditionExpression=None):
        key = Item["id"]["S"]
        if ConditionExpression and key in self.items:
            raise self.exceptions.ConditionalCheckFailedException()
        self.items[key] = Item

    def get_item(self, TableName, Key):
        item = self.items.get(Key["id"]["S"])
        return {"Item": item} if item else {}

    def get_paginator(self, name):
        items = list(self.items.values())

        class Pages:
            def paginate(self, **kwargs):
                return self

            def search(self, expression):
                return iter(items)

        return Pages()


def test_dynamo_store_round_trip_and_upcoming():
    store = DynamoDocumentStore(FakeDynamo(), "table")
    store.add(DOC)
    assert store.get(DOC.id) == DOC
    assert store.list_all() == [DOC]
    assert [u.label for u in store.upcoming(30, today=date(2026, 10, 7))] == ["Payment due"]


def test_dynamo_store_rejects_duplicate_ids_but_put_replaces():
    store = DynamoDocumentStore(FakeDynamo(), "table")
    store.add(DOC)
    with pytest.raises(ValueError):
        store.add(DOC)
    store.put(DOC.model_copy(update={"provider": "Changed"}))
    assert store.get(DOC.id).provider == "Changed"


class FakeEmbedder:
    dimensions = 3

    def embed(self, text):
        return [1.0, 0.0, 0.0]


class FakeS3Vectors:
    def __init__(self):
        self.vectors = {}

    def put_vectors(self, vectorBucketName, indexName, vectors):
        for v in vectors:
            self.vectors[v["key"]] = v

    def query_vectors(self, topK, **kwargs):
        hits = [{"key": k, "distance": 0.25, "metadata": v["metadata"]} for k, v in self.vectors.items()]
        return {"vectors": hits[:topK]}


def test_s3vectors_index_is_idempotent_and_search_reports_similarity():
    client = FakeS3Vectors()
    searcher = S3VectorsSearcher(client, FakeEmbedder(), "bucket", "passages")
    first = searcher.index(DOC)
    searcher.index(DOC)
    assert len(client.vectors) == first

    hit = searcher.search("when is the hydro bill due", top_k=1)[0]
    assert hit.document_id == DOC.id
    assert hit.score == pytest.approx(0.75)


def test_delete_removes_document_and_its_passages():
    dynamo = FakeDynamo()
    dynamo.delete_item = lambda TableName, Key, ReturnValues: {"Attributes": dynamo.items.pop(Key["id"]["S"])}
    store = DynamoDocumentStore(dynamo, "table")
    store.add(DOC)
    assert store.delete(DOC.id) == DOC
    assert store.list_all() == []

    client = FakeS3Vectors()
    client.delete_vectors = lambda vectorBucketName, indexName, keys: [client.vectors.pop(k) for k in keys]
    searcher = S3VectorsSearcher(client, FakeEmbedder(), "bucket", "passages")
    searcher.index(DOC)
    searcher.delete(DOC)
    assert client.vectors == {}
