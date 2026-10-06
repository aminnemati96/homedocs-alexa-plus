# homedocs agent

Backend for the simulated Alexa+ experience. For each question it opens an MCP
session with the homedocs server, gives its tools to a model on Bedrock (Converse
API), runs the tool calls, and streams every step to the browser. Replies are
spoken with Amazon Polly.

## Run

The MCP server must be running first (see `../mcp-server`).

```
uv sync
uv run homedocs-ask "when does my car insurance renew?"
uv run homedocs-agent
```

`homedocs-ask` prints each tool call and the answer in the terminal.
`homedocs-agent` serves the API on `http://127.0.0.1:8001`.

## API

| Endpoint | Body | Returns |
| --- | --- | --- |
| `POST /api/chat` | `{"text", "history": [{"role", "text"}]}` | Server-Sent Events: `tool_call`, `tool_result`, `answer`, `error` |
| `POST /api/speak` | `{"text"}` | MP3 audio from Polly |
| `GET /api/health` | | Model and MCP URL in use |

## Settings

| Variable | Default |
| --- | --- |
| `MCP_URL` | `http://127.0.0.1:8000/mcp` |
| `BEDROCK_MODEL_ID` | `global.anthropic.claude-haiku-4-5-20251001-v1:0` |
| `AWS_REGION` | `us-east-1` |
| `POLLY_VOICE` | `Joanna` (neural) |
| `AGENT_HOST` / `AGENT_PORT` | `127.0.0.1` / `8001` |

## Test

```
uv run pytest
```
