"""MCP server exposing household paperwork tools over Streamable HTTP."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from homedocs_mcp import config
from homedocs_mcp.store import Document, DocumentStore, SearchHit, UpcomingDate

store = DocumentStore.from_json(config.DATA_PATH)
searcher = config.make_searcher()

mcp = FastMCP(
    "homedocs",
    instructions=(
        "Answers questions about the user's household paperwork: bills, leases, "
        "warranties, insurance and ID documents. Always say which document an "
        "answer came from. Keep spoken answers to one or two sentences."
    ),
    host=config.HOST,
    port=config.PORT,
    stateless_http=True,
)


@mcp.tool(title="Search documents")
def search_documents(query: str, top_k: int = 3) -> list[SearchHit]:
    """Find passages in the user's documents that answer a question.

    Use for any question about what a bill, lease, warranty or policy says.
    """
    return searcher.search(query, top_k=max(1, min(top_k, 10)))


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
