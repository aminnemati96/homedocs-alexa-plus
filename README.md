# HomeDocs for Alexa+

Ask Alexa about your own household paperwork. "When does my car insurance renew?",
"Is my laptop still under warranty?", "Can I have a cat in my apartment?" HomeDocs
answers in a sentence or two, says which document the answer came from, and lights
the ring yellow when a bill, renewal or expiry is coming up.

Built for the Amazon "Build, Ship, Shape" hackathon, Alexa+ track, as a
**self-hosted MCP server** (spec 2025-11-25, Streamable HTTP) plus a **web app that
simulates an Alexa+ device** for the demo.

## What it does

- **Answers questions from your documents.** Semantic search over passages of your
  bills, leases, warranties, insurance policies and ID documents.
- **Reads new documents for you.** Upload a PDF or a phone photo; Bedrock pulls out
  the title, provider, key dates and a summary, and it is searchable right away.
- **Remembers things you say.** "Remember that my car registration renews May 3rd."
- **Tells you what is coming up.** On start it checks the next 14 days and shows a
  yellow notification ring, like an Echo. "What are my notifications?" reads them out.
- **Shows its work.** A side panel lists every MCP tool call live, with inputs,
  timing and results.

## Architecture

```mermaid
flowchart LR
  subgraph Browser
    UI["Alexa+ simulator<br/>(React, Web Speech mic)"]
  end
  subgraph AWS
    CF["CloudFront"]
    S3W["S3<br/>static site"]
    L["Lambda: agent API<br/>(FastAPI + Lambda Web Adapter,<br/>response streaming)"]
    BR["Bedrock<br/>Claude Haiku 4.5<br/>(Converse + tool use)"]
    PO["Polly<br/>neural voice"]
    COG["Cognito<br/>client credentials"]
    AC["Bedrock AgentCore Runtime:<br/>homedocs MCP server"]
    TI["Bedrock<br/>Titan Embeddings V2"]
    DDB["DynamoDB<br/>documents"]
    S3V["S3 Vectors<br/>passage index"]
  end
  UI --> CF
  CF -->|"/"| S3W
  CF -->|"/api/*"| L
  L --> BR
  L --> PO
  L -->|token| COG
  L -->|"MCP, Streamable HTTP + JWT"| AC
  AC --> TI
  AC --> DDB
  AC --> S3V
```

A question flows like this: the browser turns speech into text and sends it to the
agent API. The agent opens an MCP session with the HomeDocs server on AgentCore and
gives its tools to Claude on Bedrock. Claude calls tools (for example
`search_documents` or `list_upcoming_dates`), the agent runs them over MCP, and
streams every step back to the page. The final answer is spoken with Polly.

### MCP tools

| Tool | What it does |
| --- | --- |
| `search_documents` | Semantic search over document passages |
| `list_upcoming_dates` | Renewals, expiries and due dates in the next N days |
| `list_documents` | Every stored document with its key dates |
| `get_document` | Full text of one document |
| `save_document` | Store a new document or spoken note and index it |

The server works with any MCP client. The demo also shows it in MCP Inspector.

## AWS services and why

| Service | Role |
| --- | --- |
| Amazon Bedrock (Claude Haiku 4.5) | Conversation and tool use through the Converse API; reads uploaded PDFs and photos into structured fields |
| Amazon Bedrock (Titan Text Embeddings V2) | Embeds document passages and questions for semantic search |
| Amazon Bedrock AgentCore Runtime | Hosts the MCP server (MCP protocol, stateless Streamable HTTP, JWT inbound auth) |
| Amazon S3 Vectors | Serverless vector index for passages; no cluster to run |
| Amazon DynamoDB | Document store (on-demand) |
| Amazon Cognito | Machine-to-machine OAuth tokens so only the agent can call the MCP server |
| AWS Lambda | Agent API with response streaming via the Lambda Web Adapter |
| Amazon Polly | Neural voice for spoken replies |
| Amazon CloudFront + S3 | Serves the web app and routes `/api/*` to Lambda on one URL |
| AWS Secrets Manager | Holds the Cognito client secret for the Lambda |
| Amazon ECR | Container images for the MCP server and the agent |
| Amazon EventBridge Scheduler | Pings the agent every 5 minutes so the Lambda and AgentCore session stay warm |
| Amazon CloudWatch, SNS, AWS Budgets | Email alerts for failed requests, Lambda errors, throttles, traffic spikes and cost |
| AWS Resource Groups | One view of everything tagged `Project=homedocs` |

All infrastructure is Terraform in [`infra/`](infra/). Running cost at demo traffic
is a few dollars a month.

**Security choices:** the MCP server only accepts Cognito tokens from the agent's app
client; IAM roles are scoped to the one table, vector index and models they use; the
Lambda rejects requests that do not come through CloudFront; the public site needs a
demo passcode because every question costs Bedrock usage.

## Repository layout

| Folder | Contents |
| --- | --- |
| [`mcp-server/`](mcp-server/) | The MCP server (Python, MCP SDK 1.30). Runs locally with Qdrant or on AWS with DynamoDB and S3 Vectors |
| [`agent/`](agent/) | Agent API: Bedrock tool loop over MCP, document extraction, Polly |
| [`web/`](web/) | The Alexa+ simulator (React, Vite, TypeScript) |
| [`infra/`](infra/) | Terraform for everything on AWS |
| [`samples/`](samples/) | Fictional documents for testing and the demo |
| [`docs/`](docs/) | Write-up, product feedback and friction log |

## Run it locally

Needs Python 3.12+ with [uv](https://docs.astral.sh/uv/), Node 20+ with pnpm, Docker,
and AWS credentials with Bedrock access (Claude Haiku 4.5, Titan Embeddings V2) and
Polly in us-east-1.

1. `docker compose up -d qdrant` (repo root)
2. `cd mcp-server`, `uv sync`, `uv run homedocs-ingest`, then `uv run homedocs-mcp`
3. `cd agent`, `uv sync`, `uv run homedocs-agent`
4. `cd web`, `pnpm install`, `pnpm dev`, then open http://localhost:5173 in Chrome or Edge

Tests: `uv run pytest` in `mcp-server/` and `agent/` (no AWS or Docker needed), and
`pnpm typecheck` in `web/`.

## Deploy to AWS

See [`infra/README.md`](infra/README.md).

## License

[MIT](LICENSE)
