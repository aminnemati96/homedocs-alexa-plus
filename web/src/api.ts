// Client for the agent API (see agent/README.md).

export type Turn = { role: "user" | "assistant"; text: string };

export type AgentEvent =
  | { type: "tool_call"; id: string; name: string; input: Record<string, unknown> }
  | {
      type: "tool_result";
      id: string;
      name: string;
      output: unknown;
      is_error: boolean;
      ms: number;
    }
  | { type: "answer"; text: string }
  | { type: "error"; message: string };

/** POST a question and call onEvent for each Server-Sent Event as it arrives. */
export async function chat(
  text: string,
  history: Turn[],
  onEvent: (event: AgentEvent) => void,
): Promise<void> {
  const response = await fetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text, history }),
  });
  if (!response.ok || !response.body) {
    throw new Error(`Agent returned ${response.status}`);
  }

  const reader = response.body.pipeThrough(new TextDecoderStream()).getReader();
  let buffer = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += value;
    let boundary: number;
    while ((boundary = buffer.indexOf("\n\n")) >= 0) {
      const frame = buffer.slice(0, boundary);
      buffer = buffer.slice(boundary + 2);
      const data = frame
        .split("\n")
        .filter((line) => line.startsWith("data: "))
        .map((line) => line.slice(6))
        .join("\n");
      if (data) onEvent(JSON.parse(data) as AgentEvent);
    }
  }
}

/** Fetch Polly audio for a reply and play it. Resolves when playback ends. */
export async function speak(text: string): Promise<void> {
  const response = await fetch("/api/speak", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
  });
  if (!response.ok) throw new Error(`Speech failed with ${response.status}`);
  const url = URL.createObjectURL(await response.blob());
  try {
    const audio = new Audio(url);
    await new Promise<void>((resolve, reject) => {
      audio.onended = () => resolve();
      audio.onerror = () => reject(new Error("Audio playback failed"));
      audio.play().catch(reject);
    });
  } finally {
    URL.revokeObjectURL(url);
  }
}

export type UploadStep = { name: string; input: Record<string, unknown>; output: unknown; ms: number };

/** Upload a PDF or photo; the agent extracts it with Bedrock and saves it via MCP. */
export async function addDocument(file: File): Promise<{ steps: UploadStep[]; message: string }> {
  const form = new FormData();
  form.append("file", file);
  const response = await fetch("/api/documents", { method: "POST", body: form });
  const body = await response.json();
  if (!response.ok) throw new Error(body.detail ?? `Upload failed with ${response.status}`);
  return body;
}
