# homedocs MCP server

MCP server (Streamable HTTP, protocol 2025-11-25) that answers questions about
household paperwork: bills, leases, warranties, insurance and ID documents.

## Tools

| Tool | What it does |
| --- | --- |
| `search_documents` | Finds passages that answer a question (semantic search) |
| `list_upcoming_dates` | Renewals, expiries and due dates in the next N days |
| `list_documents` | Every stored document with its key dates |
| `get_document` | Full text of one document |

## How search works

Each document is split into short overlapping passages. Each passage is embedded
with Amazon Titan Text Embeddings V2 on Bedrock and stored in Qdrant. A question is
embedded the same way and matched by cosine similarity.

## Run

From the repo root, start Qdrant:

```
docker compose up -d qdrant
```

From `mcp-server/`:

```
uv sync
uv run homedocs-ingest
uv run homedocs-mcp
```

The endpoint is `http://127.0.0.1:8000/mcp`. AWS credentials come from your normal
AWS CLI setup (`AWS_PROFILE` works).

| Variable | Default | Meaning |
| --- | --- | --- |
| `HOMEDOCS_SEARCH` | `vector` | `vector` (Bedrock + Qdrant) or `keyword` (offline) |
| `HOMEDOCS_DATA` | `data/sample_documents.json` | Documents JSON file |
| `QDRANT_URL` | `http://localhost:6333` | Qdrant endpoint |
| `HOMEDOCS_COLLECTION` | `homedocs` | Qdrant collection name |
| `AWS_REGION` | `us-east-1` | Bedrock region |
| `HOMEDOCS_HOST` / `HOMEDOCS_PORT` | `127.0.0.1` / `8000` | Where the MCP server listens |

## Test

```
uv run pytest
```

Tests use Qdrant's in-memory mode and a fake embedder, so they need no Docker or AWS.
For a manual check, run `npx -y @modelcontextprotocol/inspector` and connect with
Streamable HTTP to `http://127.0.0.1:8000/mcp`.
