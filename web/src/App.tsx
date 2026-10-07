import { useRef, useState, type FormEvent } from "react";
import { addDocument, chat, speak, type Turn } from "./api";
import { listenOnce, speechSupported } from "./speech";
import Ring, { type RingState } from "./Ring";
import ToolPanel, { type ToolRun } from "./ToolPanel";

const SUGGESTIONS = [
  "What bills or renewals are coming up this month?",
  "Is my dishwasher still under warranty?",
  "Can I have a cat in my apartment?",
  "When does my car insurance renew?",
];

export default function App() {
  const [ring, setRing] = useState<RingState>("idle");
  const [turns, setTurns] = useState<Turn[]>([]);
  const [heard, setHeard] = useState("");
  const [typed, setTyped] = useState("");
  const [tools, setTools] = useState<ToolRun[]>([]);
  const [error, setError] = useState("");
  const [voiceOn, setVoiceOn] = useState(true);
  const stopListening = useRef<(() => void) | null>(null);

  const busy = ring !== "idle";

  async function ask(question: string) {
    const text = question.trim();
    if (!text) {
      setRing("idle");
      return;
    }
    const history = turns;
    setTurns([...history, { role: "user", text }]);
    setTools([]);
    setError("");
    setHeard("");
    setRing("thinking");

    let answer = "";
    try {
      await chat(text, history, (event) => {
        switch (event.type) {
          case "tool_call":
            setTools((runs) => [...runs, { id: event.id, name: event.name, input: event.input }]);
            break;
          case "tool_result":
            setTools((runs) =>
              runs.map((run) =>
                run.id === event.id
                  ? { ...run, output: event.output, isError: event.is_error, ms: event.ms }
                  : run,
              ),
            );
            break;
          case "answer":
            answer = event.text;
            setTurns((all) => [...all, { role: "assistant", text: event.text }]);
            break;
          case "error":
            setError(event.message);
            break;
        }
      });
      if (answer && voiceOn) {
        setRing("speaking");
        await speak(answer);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setRing("idle");
    }
  }

  async function onMic() {
    if (ring === "listening") {
      stopListening.current?.();
      return;
    }
    if (busy) return;
    setError("");
    setRing("listening");
    const { result, stop } = listenOnce(setHeard);
    stopListening.current = stop;
    try {
      await ask(await result);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setRing("idle");
    } finally {
      stopListening.current = null;
    }
  }

  async function onUpload(file: File) {
    if (busy) return;
    setTurns((all) => [...all, { role: "user", text: `Added ${file.name}` }]);
    setTools([{ id: "upload", name: "bedrock_extract", input: { file: file.name } }]);
    setError("");
    setRing("thinking");
    try {
      const { steps, message } = await addDocument(file);
      setTools(
        steps.map((step, i) => ({
          id: `upload-${i}`,
          name: step.name,
          input: step.input,
          output: step.output,
          isError: false,
          ms: step.ms,
        })),
      );
      setTurns((all) => [...all, { role: "assistant", text: message }]);
      if (voiceOn) {
        setRing("speaking");
        await speak(message);
      }
    } catch (e) {
      setTools([]);
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setRing("idle");
    }
  }

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (busy) return;
    const text = typed;
    setTyped("");
    void ask(text);
  }

  return (
    <div className="layout">
      <main className="device">
        <header className="brand">
          <span className="brand-name">HomeDocs</span>
          <span className="brand-sub">for Alexa+ (simulated)</span>
        </header>

        <Ring state={ring} onClick={speechSupported ? onMic : undefined} />

        <p className="status" aria-live="polite">
          {ring === "listening" && (heard || "Listening...")}
          {ring === "thinking" && "Checking your documents..."}
          {ring === "speaking" && "Speaking"}
          {ring === "idle" &&
            (speechSupported ? "Tap the ring and ask about your paperwork" : "Type a question below")}
        </p>

        <section className="conversation">
          {turns.map((turn, i) => (
            <div key={i} className={`bubble ${turn.role}`}>
              {turn.text}
            </div>
          ))}
          {error && <div className="bubble error">{error}</div>}
        </section>

        {turns.length === 0 && (
          <div className="suggestions">
            {SUGGESTIONS.map((s) => (
              <button key={s} type="button" disabled={busy} onClick={() => void ask(s)}>
                {s}
              </button>
            ))}
          </div>
        )}

        <form className="composer" onSubmit={onSubmit}>
          <input
            value={typed}
            onChange={(e) => setTyped(e.target.value)}
            placeholder="Or type a question"
            aria-label="Question"
          />
          <button type="submit" disabled={busy || !typed.trim()}>
            Ask
          </button>
          <label className={`upload ${busy ? "disabled" : ""}`} title="Add a PDF or a photo of a document">
            Add document
            <input
              type="file"
              accept="application/pdf,image/png,image/jpeg,image/webp"
              disabled={busy}
              onChange={(e) => {
                const file = e.target.files?.[0];
                e.target.value = "";
                if (file) void onUpload(file);
              }}
            />
          </label>
          <label className="voice-toggle">
            <input type="checkbox" checked={voiceOn} onChange={(e) => setVoiceOn(e.target.checked)} />
            Voice
          </label>
        </form>
      </main>

      <ToolPanel runs={tools} thinking={ring === "thinking"} />
    </div>
  );
}
