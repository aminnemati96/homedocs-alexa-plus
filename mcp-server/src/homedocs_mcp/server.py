"""MCP server exposing household paperwork tools over Streamable HTTP."""

from __future__ import annotations

from datetime import date

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from homedocs_mcp import config
from homedocs_mcp.store import (
    Document,
    KeyDate,
    SearchHit,
    UpcomingDate,
    load_documents,
    new_document_id,
)

# Hints for MCP clients (spec 2025-11-25): which tools only read, which change data.
READ_ONLY = ToolAnnotations(readOnlyHint=True, openWorldHint=False)
ADDS_DATA = ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False)
REMOVES_DATA = ToolAnnotations(readOnlyHint=False, destructiveHint=True, idempotentHint=True, openWorldHint=False)

# The Agent Skill that teaches an agent how to use these tools (agentskills.io
# format). Served as an MCP resource so any client can load it from the server.
SKILL_URI = "skill://homedocs-paperwork/SKILL.md"

store = config.make_store()  # local JSON files, or DynamoDB when deployed
searcher = config.make_searcher(store)

mcp = FastMCP(
    "homedocs",
    instructions=(
        "Answers questions about the user's household paperwork: bills, leases, "
        "warranties, insurance and ID documents. Always say which document an "
        "answer came from. Keep spoken answers to one or two sentences. The full "
        f"guide for agents is the Agent Skill at {SKILL_URI}."
    ),
    host=config.HOST,
    port=config.PORT,
    stateless_http=True,
)


@mcp.resource(
    SKILL_URI,
    name="homedocs-paperwork",
    title="HomeDocs paperwork skill",
    description="Agent Skill: how to answer paperwork questions with these tools, by voice.",
    mime_type="text/markdown",
)
def paperwork_skill() -> str:
    return config.SKILL_PATH.read_text(encoding="utf-8")


@mcp.tool(title="Search documents", annotations=READ_ONLY)
def search_documents(query: str, top_k: int = 3) -> list[SearchHit]:
    """Find passages in the user's documents that answer a question.

    Use for any question about what a bill, lease, warranty or policy says.
    """
    return searcher.search(query, top_k=max(1, min(top_k, 10)))


@mcp.tool(title="Upcoming dates", annotations=READ_ONLY)
def list_upcoming_dates(days_ahead: int = 30, today: date | None = None) -> list[UpcomingDate]:
    """List renewals, expiries and payment due dates coming up in the next N days.

    today is the user's local date (YYYY-MM-DD). Pass it when known: the server
    runs on UTC, which is already tomorrow for North American users in the evening.
    """
    return store.upcoming(days_ahead=max(1, min(days_ahead, 366)), today=today)


@mcp.tool(title="List documents", annotations=READ_ONLY)
def list_documents() -> list[Document]:
    """List every document the user has stored, with its category and key dates."""
    return store.list_all()


@mcp.tool(title="Get document", annotations=READ_ONLY)
def get_document(document_id: str) -> Document:
    """Get the full text of one document by its id."""
    doc = store.get(document_id)
    if doc is None:
        raise ValueError(f"No document with id '{document_id}'")
    return doc


@mcp.tool(title="Save document", annotations=ADDS_DATA)
def save_document(
    title: str,
    category: str,
    text: str,
    provider: str = "",
    key_dates: list[KeyDate] | None = None,
) -> Document:
    """Save a new document or note so it can be searched and reminded about later.

    Use when the user uploads a document, or explicitly asks you to remember
    something ("remember my car registration renews May 3rd"). Category is one of:
    insurance, warranty, housing, bill, identity, vehicle, medical, other.
    key_dates holds renewals, expiries and due dates as ISO dates (YYYY-MM-DD).
    """
    doc = Document(
        id=new_document_id(title),
        title=title,
        category=category,
        provider=provider,
        key_dates=key_dates or [],
        text=text,
    )
    store.add(doc)
    searcher.index(doc)
    return doc


@mcp.tool(title="Delete document", annotations=REMOVES_DATA)
def delete_document(document_id: str) -> Document:
    """Delete a document or note the user no longer needs ("forget my old lease").

    Find the id with list_documents or search_documents first, and only delete
    when the user clearly asked to.
    """
    doc = store.delete(document_id)
    if doc is None:
        raise ValueError(f"No document with id '{document_id}'")
    searcher.delete(doc)
    return doc


def admin_reset_demo() -> dict:
    """Admin only: put the documents back to the bundled samples.

    Run nightly on the public demo so one visitor's uploads don't stay for the
    next. The agent never offers admin_ tools to the model.
    """
    samples = {d.id: d for d in load_documents(config.DATA_PATH)}
    removed = 0
    for doc in store.list_all():
        if doc.id not in samples:
            store.delete(doc.id)
            searcher.delete(doc)
            removed += 1
    for doc in samples.values():
        store.put(doc)
        searcher.index(doc)
    return {"removed": removed, "samples": len(samples)}


# Registered only where it's needed (the public demo), so it doesn't show up in
# MCP Inspector or other clients during normal use.
if config.ADMIN_TOOLS:
    mcp.add_tool(admin_reset_demo, title="Reset demo data", annotations=REMOVES_DATA)


def main() -> None:
    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
