"""MCP server exposing household paperwork tools over Streamable HTTP."""

from __future__ import annotations

import os
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from homedocs_mcp.store import Document, DocumentStore, SearchHit, UpcomingDate

DEFAULT_DATA = Path(__file__).resolve().parents[2] / "data" / "sample_documents.json"

store = DocumentStore.from_json(Path(os.environ.get("HOMEDOCS_DATA", DEFAULT_DATA)))

mcp = FastMCP(
    "homedocs",
    instructions=(
        "Answers questions about the user's household paperwork: bills, leases, "
        "warranties, insurance and ID documents. Always say which document an "
        "answer came from. Keep spoken answers to one or two sentences."
    ),
    host=os.environ.get("HOMEDOCS_HOST", "127.0.0.1"),
    port=int(os.environ.get("HOMEDOCS_PORT", "8000")),
    stateless_http=True,
)


@mcp.tool(title="Search documents")
def search_documents(query: str, top_k: int = 3) -> list[SearchHit]:
    """Find passages in the user's documents that answer a question.

    Use for any question about what a bill, lease, warranty or policy says.
    """
    return store.search(query, top_k=max(1, min(top_k, 10)))


@mcp.tool(title="Upcoming dates")
def list_upcoming_dates(days_ahead: int = 30) -> list[UpcomingDate]:
    """List renewals, expiries and payment due dates coming up in the next N days."""
    return store.upcoming(days_ahead=max(1, min(days_ahead, 366)))


@mcp.tool(title="List documents")
def list_documents() -> list[Document]:
    """List every document the user has stored, with its category and key dates."""
    return store.list_all()


@mcp.tool(title="Get document")
def get_document(document_id: str) -> Document:
    """Get the full text of one document by its id."""
    doc = store.get(document_id)
    if doc is None:
        raise ValueError(f"No document with id '{document_id}'")
    return doc


def main() -> None:
    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
