export type RingState = "idle" | "listening" | "thinking" | "speaking";

const LABELS: Record<RingState, string> = {
  idle: "Start listening",
  listening: "Stop listening",
  thinking: "Thinking",
  speaking: "Stop speaking",
};

/**
 * The light ring, styled after an Echo device. Clicking it toggles the mic,
 * or interrupts the reply while it is speaking.
 * `notify` glows yellow while idle, the way an Echo shows a pending notification.
 */
export default function Ring({
  state,
  notify = false,
  checking = false,
  onClick,
}: {
  state: RingState;
  notify?: boolean;
  checking?: boolean;
  onClick?: () => void;
}) {
  return (
    <button
      type="button"
      className={`ring ring-${state}${checking ? " ring-checking" : notify ? " ring-notify" : ""}`}
      onClick={onClick}
      disabled={!onClick || state === "thinking"}
      aria-label={notify ? `${LABELS[state]} (you have notifications)` : LABELS[state]}
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
