export type RingState = "idle" | "listening" | "thinking" | "speaking";

const LABELS: Record<RingState, string> = {
  idle: "Start listening",
  listening: "Stop listening",
  thinking: "Thinking",
  speaking: "Speaking",
};

/** The light ring, styled after an Echo device. Clicking it toggles the mic. */
export default function Ring({ state, onClick }: { state: RingState; onClick?: () => void }) {
  return (
    <button
      type="button"
      className={`ring ring-${state}`}
      onClick={onClick}
      disabled={!onClick || state === "thinking" || state === "speaking"}
      aria-label={LABELS[state]}
    >
      <span className="ring-glow" />
      <span className="ring-core">
        <svg viewBox="0 0 24 24" width="40" height="40" aria-hidden="true">
          <path
            fill="currentColor"
            d="M12 14a3 3 0 0 0 3-3V5a3 3 0 1 0-6 0v6a3 3 0 0 0 3 3Zm5-3a5 5 0 0 1-10 0H5a7 7 0 0 0 6 6.92V21h2v-3.08A7 7 0 0 0 19 11h-2Z"
          />
        </svg>
      </span>
    </button>
  );
}
