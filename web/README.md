# homedocs web simulator

A web page that simulates an Alexa+ device: tap the light ring and speak, or type.
The right-hand panel shows each MCP tool call live.

- **Ring states:** blue spin while starting up, cyan pulse while listening, spinning
  while thinking, glowing while speaking, and yellow when a notification is waiting.
  Tap it while it's speaking to interrupt.
- **Speech to text:** the browser's Web Speech API (Chrome or Edge).
- **Spoken replies:** the answer streams in, and each finished sentence is sent to
  Amazon Polly (through the agent's `/api/speak`) while the next is still being written.
- **Notifications:** on start the page checks the next 14 days. The "What are my
  notifications?" chip plays a summary prepared in advance; anything typed or spoken
  goes to the model.
- **Documents:** "Add document" uploads a PDF or photo for Bedrock to read and save.
- `/api/*` is proxied to the agent on `http://127.0.0.1:8001` in development (see
  `vite.config.ts`). The production build asks for the demo passcode
  (`.env.production`).

## Run

Start Qdrant, the MCP server and the agent first, then:

```
pnpm install
pnpm dev
```

Open http://localhost:5173 in Chrome or Edge and allow the microphone.

`pnpm typecheck` checks types; `pnpm build` makes a static build in `dist/`.
