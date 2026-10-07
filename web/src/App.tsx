import { useEffect, useRef, useState, type FormEvent } from "react";
import {
  addDocument,
  chat,
  getNotifications,
  passcodeMissing,
  PasscodeRequired,
  setPasscode,
  speak,
  type Notification,
  type Turn,
} from "./api";
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
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [notificationsHeard, setNotificationsHeard] = useState(false);
  const [needPasscode, setNeedPasscode] = useState(passcodeMissing);
  const [passcodeInput, setPasscodeInput] = useState("");
  // True until the first notification check finishes: the ring spins slowly in
  // blue, like an Echo starting up, so the cold-start wait looks deliberate.
  const [checking, setChecking] = useState(false);
  const stopListening = useRef<(() => void) | null>(null);

  const busy = ring !== "idle";
  const notify = !busy && !notificationsHeard && notifications.length > 0;

  // Like an Echo: check for due dates on start and light the ring yellow if any.
  // The check is a plain MCP tool call, shown in the panel so viewers can see it.
  async function refreshNotifications(showInPanel: boolean) {
    if (showInPanel) setChecking(true);
    try {
      const { items, tool } = await getNotifications();
      setNotifications(items);
      if (showInPanel) {
        setTools([{ id: "notifications", name: tool.name, input: tool.input, output: tool.output, isError: false, ms: tool.ms }]);
      }
    } catch (e) {
      // Notifications are a nice-to-have; the page works without them.
      if (e instanceof PasscodeRequired) setNeedPasscode(true);
    } finally {
      if (showInPanel) setChecking(false);
    }
  }

  useEffect(() => {
    if (!passcodeMissing()) void refreshNotifications(true);
  }, []);

  async function ask(question: string) {
    const text = question.trim();
    if (!text) {
      setRing("idle");
      return;
    }
    const history = turns;
    if (/notification|coming up|due soon/i.test(text)) setNotificationsHeard(true);
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
      if (e instanceof PasscodeRequired) setNeedPasscode(true);
      else setError(e instanceof Error ? e.message : String(e));
    } finally {
      setRing("idle");
      // The answer may have saved a new document with new dates.
      void refreshNotifications(false);
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
      if (e instanceof PasscodeRequired) setNeedPasscode(true);
      else setError(e instanceof Error ? e.message : String(e));
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
      if (e instanceof PasscodeRequired) setNeedPasscode(true);
      else setError(e instanceof Error ? e.message : String(e));
    } finally {
      setRing("idle");
      setNotificationsHeard(false);
      void refreshNotifications(false);
    }
  }

  function onPasscode(event: FormEvent) {
    event.preventDefault();
    setPasscode(passcodeInput.trim());
    setNeedPasscode(false);
    void refreshNotifications(true);
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

        <Ring state={ring} notify={notify} checking={checking} onClick={speechSupported ? onMic : undefined} />

        <p className="status" aria-live="polite">
          {ring === "listening" && (heard || "Listening...")}
          {ring === "thinking" && "Checking your documents..."}
          {ring === "speaking" && "Speaking"}
          {ring === "idle" && checking && "Checking for updates..."}
          {ring === "idle" &&
            !checking &&
            (notify
              ? `You have ${notifications.length} notification${notifications.length === 1 ? "" : "s"}. Ask "what are my notifications?"`
              : speechSupported
                ? "Tap the ring and ask about your paperwork"
                : "Type a question below")}
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
            {(notify ? ["What are my notifications?", ...SUGGESTIONS] : SUGGESTIONS).map((s) => (
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

      {needPasscode && (
        <div className="overlay" role="dialog" aria-modal="true" aria-labelledby="passcode-title">
          <form className="passcode" onSubmit={onPasscode}>
            <h2 id="passcode-title">Demo passcode</h2>
            <p>This demo uses paid AWS services, so it needs the passcode from the project page.</p>
            <input
              type="password"
              value={passcodeInput}
              onChange={(e) => setPasscodeInput(e.target.value)}
              aria-label="Passcode"
              autoFocus
            />
            <button type="submit" disabled={!passcodeInput.trim()}>
              Continue
            </button>
          </form>
        </div>
      )}
    </div>
  );
}
