// Client for the agent API (see agent/README.md).

export type Turn = { role: "user" | "assistant"; text: string };

// The deployed site asks for a demo passcode; it is kept in this browser only.
const PASSCODE_KEY = "homedocs-passcode";

export class PasscodeRequired extends Error {
  constructor() {
    super("Passcode required");
  }
}

let sessionPasscode = "";

export function setPasscode(passcode: string): void {
  try {
    localStorage.setItem(PASSCODE_KEY, passcode);
  } catch {
    // Storage can be blocked (private mode); the passcode then lasts for this page only.
  }
  sessionPasscode = passcode;
}

/**
 * True on the deployed site when no passcode is saved yet, so the prompt can
 * show right away instead of after the first API call fails (which can take a
 * few seconds while Lambda starts). Set in web/.env.production.
 */
export function passcodeMissing(): boolean {
  return import.meta.env.VITE_REQUIRE_PASSCODE === "true" && !getPasscode();
}

function getPasscode(): string {
  try {
    return localStorage.getItem(PASSCODE_KEY) ?? sessionPasscode;
  } catch {
    return sessionPasscode;
  }
}

/** fetch() plus the passcode header; throws PasscodeRequired on 401. */
async function apiFetch(url: string, init: RequestInit = {}): Promise<Response> {
  const headers = new Headers(init.headers);
  const passcode = getPasscode();
  if (passcode) headers.set("X-Demo-Passcode", passcode);
  const response = await fetch(url, { ...init, headers });
  if (response.status === 401) throw new PasscodeRequired();
  return response;
}

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
  const response = await apiFetch("/api/chat", {
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

/** Fetch Polly audio (MP3) for some text. */
export async function synthesize(text: string): Promise<Blob> {
  const response = await apiFetch("/api/speak", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
  });
  if (!response.ok) throw new Error(`Speech failed with ${response.status}`);
  return response.blob();
}

/** Fetch Polly audio for a reply and play it. Resolves when playback ends. */
export async function speak(text: string): Promise<void> {
  await playAudio(await synthesize(text));
}

/** Play audio that was already fetched. Resolves when playback ends. */
export async function playAudio(blob: Blob): Promise<void> {
  const url = URL.createObjectURL(blob);
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
  const response = await apiFetch("/api/documents", { method: "POST", body: form });
  const body = await response.json();
  if (!response.ok) throw new Error(body.detail ?? `Upload failed with ${response.status}`);
  return body;
}

export type Notification = { document_id: string; title: string; label: string; date: string; days_away: number };

/** Upcoming dates for the notification ring, plus the MCP call that produced them. */
export async function getNotifications(): Promise<{ items: Notification[]; tool: UploadStep }> {
  const response = await apiFetch("/api/notifications");
  const body = await response.json();
  if (!response.ok) throw new Error(body.detail ?? `Notifications failed with ${response.status}`);
  return body;
}
