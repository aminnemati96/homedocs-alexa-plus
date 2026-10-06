# Alexa+ hackathon entry (working title)

Entry for the Amazon "Build, Ship, Shape" hackathon, Alexa+ track.
Deadline: Friday, October 23, 2026, 12:00 PM PDT.
Rules: https://amazonappdev2026.devpost.com/rules (checked 2026-10-06).

## What the rules require (Alexa+ track)

- A self-hosted MCP server (spec 2025-11-25 or later, Streamable HTTP) or an Agent Skill.
  A simulated Alexa+ experience in a web app is also accepted.
- Demo video under 3 minutes, public on YouTube or Vimeo.
- Code repo (public with a visible open-source license, or private and shared with Devpost/Amazon).
- Text description, product feedback on the Amazon tools used, track and mini challenge selection.
- Optional friction log: up to a 10% bonus at screening.
- Judged equally on Tech Implementation, Design, Potential Impact, Quality of Idea.
- Project must be new or significantly updated after August 31, 2026.
- One project can win at most one track prize plus one mini challenge prize
  (AWS Builder or Open Source, not both).

## Plan

Build a real MCP server (so it qualifies on the main path) and also a web app that
simulates Alexa+ (so the demo works without an Echo device).

```
browser (mic + chat)  ->  web app backend  ->  Bedrock (Converse API, tool use)
                                                   |
                                                   v
                                     MCP server (Streamable HTTP)  ->  data store
```

The same MCP server is also shown in MCP Inspector in the video.

## Idea

Home paperwork memory: ask Alexa about your own bills, leases, warranties and
insurance ("when does my car insurance renew?") and get answers that name the
source document.

## Folder layout

- `mcp-server/`  Python MCP server, Streamable HTTP; Bedrock Titan embeddings + Qdrant
- `agent/`       Python FastAPI backend: Bedrock Converse tool loop over the MCP tools, Polly voice
- `web/`         React (Vite) "Alexa" simulator: mic input, chat, live tool-call panel
- `docs/`        write-up, product feedback, friction log notes (to do)

## Run everything locally

Four terminals, in this order:

1. `docker compose up -d qdrant` (repo root)
2. `cd mcp-server`, `uv run homedocs-ingest` once, then `uv run homedocs-mcp`
3. `cd agent`, `uv run homedocs-agent`
4. `cd web`, `pnpm dev`, then open http://localhost:5173 in Chrome or Edge

## Open questions

- Mini challenge: AWS Builder (Bedrock) is the plan; the repo is still open source.
- MCP Python SDK 1.30.0 sets LATEST_PROTOCOL_VERSION to 2025-11-25 (checked on GitHub).

## Friction log

Keep notes here while building (task, steps, expected vs actual, severity, workaround).

- 2026-10-06, Bedrock + `aws login`: boto3 failed to load credentials from `aws login`
  until `botocore[crt]` was installed. The error names the fix, but nothing in the
  Bedrock getting-started path mentions it. Workaround: depend on `boto3[crt]`.
- 2026-10-06, Bedrock Converse with Claude Haiku 4.5: the first call returned a tool
  use, then the next call failed with ResourceNotFoundException asking for the
  Anthropic use-case form. Expected the form requirement before any call succeeded,
  and a clearer error type than "not found". Workaround: submit the form, wait ~15 min.
