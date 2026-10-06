# homedocs web simulator

A web page that simulates an Alexa+ device: tap the light ring and speak, or type.
The right-hand panel shows each MCP tool call live.

- Speech to text: the browser's Web Speech API (Chrome or Edge).
- Spoken replies: Amazon Polly, through the agent's `/api/speak`.
- `/api/*` is proxied to the agent on `http://127.0.0.1:8001` (see `vite.config.ts`).

## Run

Start Qdrant, the MCP server and the agent first, then:

```
pnpm install
pnpm dev
```

Open http://localhost:5173 in Chrome or Edge and allow the microphone.

`pnpm typecheck` checks types; `pnpm build` makes a static build in `dist/`.
