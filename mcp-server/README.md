# homedocs MCP server

MCP server (Streamable HTTP, protocol 2025-11-25, stateless) that answers questions
about household paperwork: bills, leases, warranties, insurance and ID documents.

## Tools

| Tool | What it does | Annotation |
| --- | --- | --- |
| `search_documents` | Finds passages that answer a question (semantic search) | read-only |
| `list_upcoming_dates` | Renewals, expiries and due dates in the next N days, from the user's local date | read-only |
| `list_documents` | Every stored document with its key dates | read-only |
| `get_document` | Full text of one document | read-only |
| `save_document` | Stores a new document or note and indexes it | adds data |
| `delete_document` | Removes a document and its passages | removes data |
| `admin_reset_demo` | Restores the sample documents (only when `HOMEDOCS_ADMIN_TOOLS=true`) | removes data |

## Agent Skill

[`skills/homedocs-paperwork/SKILL.md`](skills/homedocs-paperwork/SKILL.md) tells an
agent how to use these tools by voice ([Agent Skills](https://agentskills.io) format).
The server also serves it as the MCP resource `skill://homedocs-paperwork/SKILL.md`.

## How search works

Each document is split into short overlapping passages. Each passage is embedded
with Amazon Titan Text Embeddings V2 on Bedrock and stored in a vector index
(Qdrant locally, Amazon S3 Vectors on AWS). A question is embedded the same way and
matched by cosine similarity.

## Run locally

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
AWS CLI setup (`AWS_PROFILE` works). Documents you add are saved to
`data/user_documents.json`, which git ignores.

## Settings

| Variable | Default | Meaning |
| --- | --- | --- |
| `HOMEDOCS_STORE` | `file` | `file` (JSON files) or `dynamodb` |
| `HOMEDOCS_SEARCH` | `vector` | `vector` (Qdrant), `s3vectors`, or `keyword` (offline) |
| `HOMEDOCS_DATA` | `data/sample_documents.json` | Sample documents |
| `HOMEDOCS_USER_DATA` | `data/user_documents.json` | Documents added locally |
| `QDRANT_URL` / `HOMEDOCS_COLLECTION` | `http://localhost:6333` / `homedocs` | Qdrant |
| `HOMEDOCS_TABLE` | `homedocs-documents` | DynamoDB table |
| `HOMEDOCS_VECTOR_BUCKET` / `HOMEDOCS_VECTOR_INDEX` | none / `passages` | S3 Vectors |
| `HOMEDOCS_ADMIN_TOOLS` | off | `true` registers `admin_reset_demo` |
| `AWS_REGION` | `us-east-1` | Bedrock and storage region |
| `HOMEDOCS_HOST` / `HOMEDOCS_PORT` | `127.0.0.1` / `8000` | Where the server listens |

The `Dockerfile` builds the ARM64 image that runs on Bedrock AgentCore Runtime with
`dynamodb` and `s3vectors` (see `../infra`).

## Test

```
uv run pytest
```

Tests use Qdrant's in-memory mode and fakes for AWS, so they need no Docker or AWS.
For a manual check, run `npx -y @modelcontextprotocol/inspector` and connect with
Streamable HTTP to `http://127.0.0.1:8000/mcp`.
