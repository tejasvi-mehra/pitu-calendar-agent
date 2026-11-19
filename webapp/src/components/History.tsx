import { useEffect, useRef, useState } from "react";
import { copy } from "../lib/copy";
import type { Turn } from "../lib/types";
import { GoogleMark } from "./GoogleMark";

function SpeakGlyph({ playing }: { playing: boolean }) {
  return playing ? (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
      <rect x="7" y="7" width="10" height="10" rx="1.5" />
    </svg>
  ) : (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
      <path d="M5 9v6h4l5 4V5L9 9H5z" strokeLinejoin="round" />
      <path d="M17 9.5a4 4 0 0 1 0 5" strokeLinecap="round" />
    </svg>
  );
}

export function History({
  turns,
  speakingIndex,
  onSpeak,
  onStop,
}: {
  turns: Turn[];
  speakingIndex: number | null;
  onSpeak: (index: number) => void;
  onStop: () => void;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const [locked, setLocked] = useState(false);
  const lastCount = useRef(0);

  useEffect(() => {
    if (turns.length === lastCount.current) return;
    lastCount.current = turns.length;
    const el = ref.current;
    if (el && !locked) el.scrollTop = el.scrollHeight;
  }, [turns.length, locked]);

  function onScroll() {
    const el = ref.current;
    if (!el) return;
    setLocked(el.scrollHeight - el.scrollTop - el.clientHeight > 64);
  }

  if (turns.length === 0) {    return (
      <section className="history">
        <div className="empty">
          <p className="empty-title">{copy.emptyTitle}</p>
          <p className="empty-hint">{copy.emptyHint}</p>
        </div>
      </section>
    );
  }

  const lastAssistant = [...turns].reverse().find((t) => t.role === "assistant");

  return (
    <section className="history" ref={ref} onScroll={onScroll}>
      {turns.map((turn, i) => (
        <article className={turn.role === "user" ? "turn turn-user" : "turn turn-assistant"} key={turn.at}>
          <span className="turn-avatar" aria-hidden="true">
            {turn.role === "user" ? <GoogleMark size={18} /> : <img src="/logo.png" alt="" width={20} />}
          </span>
          <div className="turn-body">
            <div className="turn-label">
              <span>{turn.role === "user" ? copy.you : copy.assistant}</span>
              <span className="turn-time">
                {new Date(turn.at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
              </span>
            </div>
            <div className="bubble">
              <p className="turn-text">{turn.text}</p>
            </div>
            {turn.role === "assistant" && (
              <button
                className="read"
                onClick={() => (speakingIndex === i ? onStop() : onSpeak(i))}
                aria-label={speakingIndex === i ? copy.stopReading : copy.readAloud}
              >                <SpeakGlyph playing={speakingIndex === i} />
                {speakingIndex === i ? copy.stopReading : copy.readAloud}
              </button>
            )}
          </div>
        </article>
      ))}
      {locked && (
        <button
          className="jump"
          aria-label="Jump to newest"
          onClick={() => {
            const el = ref.current;
            if (el) el.scrollTop = el.scrollHeight;
            setLocked(false);
          }}
        >
          <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
            <path d="M12 5v14M5 12l7 7 7-7" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </button>
      )}
      <p className="sr-only" role="status" aria-live="polite">
        {lastAssistant?.text ?? ""}
      </p>
    </section>
  );
}
