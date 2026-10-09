# homedocs agent

Backend for the simulated Alexa+ experience. For each question it opens an MCP
session with the homedocs server, loads the server's Agent Skill as its
instructions, gives the tools to Claude on Bedrock (ConverseStream API), runs the
tool calls, and streams every step and every word of the answer to the browser.
Replies are spoken with Amazon Polly.

## Run

The MCP server must be running first (see `../mcp-server`).

```
uv sync
uv run homedocs-ask "when does my car insurance renew?"
uv run homedocs-agent
```

`homedocs-ask` prints each tool call and streams the answer in the terminal.
`homedocs-agent` serves the API on `http://127.0.0.1:8001`.

## API

| Endpoint | Body | Returns |
| --- | --- | --- |
| `POST /api/chat` | `{"text", "history", "today"}` | Server-Sent Events: `answer_delta`, `tool_call`, `tool_result`, `answer`, `error` |
| `POST /api/speak` | `{"text"}` | MP3 audio from Polly |
| `POST /api/documents` | multipart `file` (PDF, PNG, JPEG, WebP) and `today` | The extracted and saved document, with both steps |
| `GET /api/notifications?today=` | | Dates due in the next 14 days, straight from the MCP server |
| `GET /api/health` | | Model and MCP URL in use |
| `POST /events` | `{"task": "warmup" or "reset", "token"}` | Scheduled jobs (EventBridge, through a direct Lambda invoke) |

`today` is the browser's local date; the servers run on UTC.

## Settings

| Variable | Default |
| --- | --- |
| `MCP_URL` | `http://127.0.0.1:8000/mcp` |
| `BEDROCK_MODEL_ID` | `global.anthropic.claude-haiku-4-5-20251001-v1:0` |
| `AWS_REGION` | `us-east-1` |
| `POLLY_VOICE` | `Joanna` (neural) |
| `AGENT_HOST` / `AGENT_PORT` | `127.0.0.1` / `8001` |
| `COGNITO_TOKEN_URL`, `COGNITO_CLIENT_ID`, `COGNITO_SCOPE` | empty (no sign-in, for a local MCP server) |
| `COGNITO_CLIENT_SECRET` or `COGNITO_CLIENT_SECRET_ARN` | Secret value, or its Secrets Manager ARN |
| `DEMO_PASSCODE` | empty (off); visitors send it as `X-Demo-Passcode` |
| `ORIGIN_SECRET` | empty (off); CloudFront sends it as `X-Origin-Verify`, schedules send it as `token` |
| `MCP_RUNTIME_VERSION` | set by Terraform so each MCP deploy starts a fresh AgentCore session |

On Lambda all of these are set by `../infra/agent.tf`.

## Test

```
uv run pytest
```

`evals/scenarios.py` runs 37 end-to-end checks against a live MCP server and real
Bedrock: notifications and follow-ups, answers with known facts, unknown questions,
save, recall and delete by voice, upload extraction, MCP tool edge cases, and that
"remove" inside an ordinary question never deletes anything. It checks what actually
happened (tools called, documents stored), not just what the model said, and cleans
up after itself.

```
uv run python evals/scenarios.py
```
