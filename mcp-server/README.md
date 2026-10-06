# homedocs MCP server

MCP server (Streamable HTTP, protocol 2025-11-25) that answers questions about
household paperwork: bills, leases, warranties, insurance and ID documents.

## Tools

| Tool | What it does |
| --- | --- |
| `search_documents` | Finds passages that answer a question |
| `list_upcoming_dates` | Renewals, expiries and due dates in the next N days |
| `list_documents` | Every stored document with its key dates |
| `get_document` | Full text of one document |

Search is keyword based for now. It will move to Bedrock embeddings and Qdrant.

## Run

```
uv sync
uv run homedocs-mcp
```

The endpoint is `http://127.0.0.1:8000/mcp`. Settings come from environment variables:
`HOMEDOCS_HOST`, `HOMEDOCS_PORT`, `HOMEDOCS_DATA` (path to a documents JSON file).

## Test

```
uv run pytest
npx -y @modelcontextprotocol/inspector
```

In Inspector, pick the Streamable HTTP transport and connect to `http://127.0.0.1:8000/mcp`.
