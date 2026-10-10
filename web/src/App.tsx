import { useEffect, useRef, useState, type FormEvent } from "react";
import {
  addDocument,
  chat,
  getNotifications,
  passcodeMissing,
  PasscodeRequired,
  playAudio,
  setPasscode,
  speak,
  stopAudio,
  synthesize,
  type Notification,
  type Turn,
} from "./api";
import { describeNotifications } from "./notifications";
import { listenOnce, speechSupported } from "./speech";
import { SpeechQueue } from "./speechQueue";
import Ring, { type RingState } from "./Ring";
import ToolPanel, { type ToolRun } from "./ToolPanel";

const SUGGESTIONS = [
  "What bills or renewals are coming up this month?",
  "Is my dishwasher still under warranty?",
  "Can I have a cat in my apartment?",
  "When does my car insurance renew?",
];

function notificationKey(n: Notification): string {
  return `${n.document_id}|${n.label}|${n.date}`;
}

export default function App() {
  const [ring, setRing] = useState<RingState>("idle");
  const [turns, setTurns] = useState<Turn[]>([]);
  const [heard, setHeard] = useState("");
  const [typed, setTyped] = useState("");
  const [tools, setTools] = useState<ToolRun[]>([]);
  const [error, setError] = useState("");
  const [voiceOn, setVoiceOn] = useState(true);
  const [notifications, setNotifications] = useState<Notification[]>([]);
  // Notifications already read out, by "document|label|date". The ring only turns
  // yellow for ones the user hasn't heard, so adding a document that has no new
  // near-term date doesn't light it up again.
  const [heardKeys, setHeardKeys] = useState<Set<string>>(new Set());
  const [needPasscode, setNeedPasscode] = useState(passcodeMissing);
  const [passcodeInput, setPasscodeInput] = useState("");
  // True until the first notification check finishes: the ring spins slowly in
  // blue, like an Echo starting up, so the cold-start wait looks deliberate.
  const [checking, setChecking] = useState(false);
  const stopListening = useRef<(() => void) | null>(null);
  // The last notification check, and its spoken summary fetched in advance, so
  // "what are my notifications?" is answered instantly without a new lookup.
  const lastCheck = useRef<ToolRun | null>(null);
  const briefing = useRef<{ text: string; audio: Promise<Blob> | null } | null>(null);
  const activeQueue = useRef<SpeechQueue | null>(null);

  const busy = ring !== "idle";
  const unheard = notifications.filter((n) => !heardKeys.has(notificationKey(n)));
  const notify = !busy && unheard.length > 0;

  function markNotificationsHeard() {
    setHeardKeys((keys) => new Set([...keys, ...notifications.map(notificationKey)]));
  }

  // Like an Echo: check for due dates on start and light the ring yellow if any.
  // The check is a plain MCP tool call, shown in the panel so viewers can see it.
  async function refreshNotifications(showInPanel: boolean) {
    if (showInPanel) setChecking(true);
    try {
      const { items, tool } = await getNotifications();
      setNotifications(items);
      const run: ToolRun = { id: "notifications", name: tool.name, input: tool.input, output: tool.output, isError: false, ms: tool.ms };
      lastCheck.current = run;
      const text = describeNotifications(items);
      if (briefing.current?.text !== text) {
        const audio = voiceOn && items.length > 0 ? synthesize(text) : null;
        audio?.catch(() => {}); // a failed prefetch just means we fetch again on demand
        briefing.current = { text, audio };
      }
      if (showInPanel) setTools([run]);
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

  /** Read notifications from the last check: no model call, no new MCP lookup. */
  async function readNotifications(question: string) {
    const summary = briefing.current?.text ?? describeNotifications(notifications);
    markNotificationsHeard();
    setTurns((all) => [...all, { role: "user", text: question }, { role: "assistant", text: summary }]);
    if (lastCheck.current) {
      setTools([{ ...lastCheck.current, input: { ...lastCheck.current.input, from: "startup check" } }]);
    }
    setError("");
    setHeard("");
    if (!voiceOn) {
      setRing("idle");
      return;
    }
    setRing("speaking");
    try {
      const audio = briefing.current?.text === summary && briefing.current.audio ? briefing.current.audio : synthesize(summary);
      await playAudio(await audio);
    } catch (e) {
      if (e instanceof PasscodeRequired) setNeedPasscode(true);
      else setError(e instanceof Error ? e.message : String(e));
    } finally {
      setRing("idle");
    }
  }

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

    // Speak sentence by sentence as the answer streams in.
    const queue = voiceOn ? new SpeechQueue(() => setRing("speaking")) : null;
    activeQueue.current = queue;
    let streamed = false;
    try {
      await chat(text, history, (event) => {
        switch (event.type) {
          case "answer_delta":
            queue?.push(event.text);
            if (!streamed) {
              streamed = true;
              setTurns((all) => [...all, { role: "assistant", text: event.text }]);
            } else {
              setTurns((all) => [...all.slice(0, -1), { role: "assistant", text: all[all.length - 1].text + event.text }]);
            }
            break;
          case "tool_call":
            setTools((runs) => [...runs, { id: event.id, name: event.name, input: event.input }]);
            // If the answer reads out upcoming dates, the notifications have been
            // heard, whatever the question was ("hello" can trigger it too).
            if (event.name === "list_upcoming_dates") markNotificationsHeard();
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
            if (!streamed) queue?.push(event.text);
            setTurns((all) => [...(streamed ? all.slice(0, -1) : all), { role: "assistant", text: event.text }]);
            streamed = true;
            break;
          case "error":
            setError(event.message);
            break;
        }
      });
      await queue?.finish();
    } catch (e) {
      if (e instanceof PasscodeRequired) setNeedPasscode(true);
      else setError(e instanceof Error ? e.message : String(e));
    } finally {
      activeQueue.current = null;
      setRing("idle");
      // The answer may have saved or deleted a document, changing the dates.
      void refreshNotifications(false);
    }
  }

  async function onMic() {
    if (ring === "listening") {
      stopListening.current?.();
      return;
    }
    if (ring === "speaking") {
      // Tap to interrupt, like Alexa.
      activeQueue.current?.stop();
      stopAudio();
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
          {ring === "speaking" && "Speaking. Tap the ring to stop."}
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
            {/* The notifications chip is a button press, so it plays the summary
                prepared after the startup check. Anything typed or spoken goes to
                the model, which understands any wording and has the conversation. */}
            {notify && lastCheck.current && (
              <button type="button" className="chip-notify" disabled={busy} onClick={() => void readNotifications("What are my notifications?")}>
                What are my notifications?
              </button>
            )}
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
        <p className="demo-note">
          Demo data: the sample documents use dates relative to today, so something is always
          coming up. Anything you add is cleared nightly.
        </p>
      </main>

      <ToolPanel runs={tools} thinking={ring === "thinking"} />

      {needPasscode && (
        <div className="overlay" role="dialog" aria-modal="true" aria-labelledby="passcode-title">
          <form className="passcode" onSubmit={onPasscode}>
            <h2 id="passcode-title">Demo passcode</h2>
            <p>This demo uses paid AWS services, so it needs a passcode.</p>
            <p>
              Judges: it is in the Devpost submission, under <strong>Additional info</strong>, at the
              top of the AWS services answer.
            </p>
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
