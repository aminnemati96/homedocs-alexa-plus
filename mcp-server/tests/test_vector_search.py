"""Vector search against Qdrant's in-memory mode with a fake embedder,
so these run without Docker or AWS."""

from pathlib import Path

from qdrant_client import QdrantClient

from homedocs_mcp.store import load_documents
from homedocs_mcp.vector_search import VectorSearcher, split_passages

DATA = Path(__file__).resolve().parents[1] / "data" / "sample_documents.json"
VOCAB = ["insurance", "renew", "dishwasher", "warranty", "rent", "lease", "passport", "wi-fi"]


class BagOfWordsEmbedder:
    dimensions = len(VOCAB)

    def embed(self, text: str) -> list[float]:
        lowered = text.lower()
        vector = [float(lowered.count(word)) for word in VOCAB]
        return vector if any(vector) else [1e-6] * self.dimensions


def make_searcher() -> VectorSearcher:
    searcher = VectorSearcher(QdrantClient(":memory:"), BagOfWordsEmbedder(), "test")
    searcher.ensure_collection()
    for doc in load_documents(DATA):
        searcher.index(doc)
    return searcher


def test_split_passages_overlaps_sentences():
    text = "One. Two. Three. Four. Five."
    assert split_passages(text, sentences_per_passage=3, overlap=1) == [
        "One. Two. Three.",
        "Three. Four. Five.",
    ]


def test_split_passages_short_text_is_one_passage():
    assert split_passages("Only one sentence.") == ["Only one sentence."]


def test_search_returns_matching_passage():
    hits = make_searcher().search("is my dishwasher under warranty", top_k=1)
    assert hits[0].document_id == "dishwasher-warranty"


def test_reindexing_replaces_old_passages():
    searcher = make_searcher()
    doc = load_documents(DATA)[0]
    first = searcher.index(doc)
    second = searcher.index(doc)
    total = searcher._qdrant.count("test").count
    assert first == second
    assert total == sum(len(split_passages(d.text)) for d in load_documents(DATA))
