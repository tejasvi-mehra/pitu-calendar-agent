import { copy } from "../lib/copy";
import { formatOffset, zoneDisplay, zones } from "../lib/zones";

export function Composer({
  value,
  onChange,
  onSubmit,
  onMic,
  listening,
  micSupported,
  busy,
  tz,
  onTzChange,
  tzEditing,
  onTzEdit,
  onTzClose,
}: {
  value: string;
  onChange: (v: string) => void;
  onSubmit: () => void;
  onMic: () => void;
  listening: boolean;
  micSupported: boolean;
  busy: boolean;
  tz: string;
  onTzChange: (tz: string) => void;
  tzEditing: boolean;
  onTzEdit: () => void;
  onTzClose: () => void;
}) {
  return (
    <section className={busy ? "composer is-busy" : "composer"}>
      {busy && <div className="progress" aria-hidden="true" />}
      {micSupported && (
        <button
          className="mic"
          onClick={onMic}
          aria-pressed={listening}
          aria-label={listening ? copy.micStop : copy.micStart}
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
            <rect x="9" y="3" width="6" height="11" rx="3" />
            <path d="M5 11a7 7 0 0 0 14 0M12 18v3" strokeLinecap="round" />
          </svg>
        </button>
      )}
      <textarea
        className="field"
        rows={1}
        aria-label={copy.placeholder}
        placeholder={copy.placeholder}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
            e.preventDefault();
            onSubmit();
          }
        }}
        onInput={(e) => {
          const el = e.currentTarget;
          el.style.height = "auto";
          el.style.height = `${Math.min(el.scrollHeight, 132)}px`;
        }}
      />
      <button className="send" onClick={onSubmit} disabled={busy || !value.trim()} aria-label={copy.send}>
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
          <path d="M5 12h14M13 6l6 6-6 6" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </button>
      <div className="tz">
        {tzEditing ? (
          <select
            className="tz-select"
            aria-label={copy.timezone}
            value={tz}
            onChange={(e) => onTzChange(e.target.value)}
            autoFocus
            onBlur={onTzClose}
          >
            {zones().map((z) => (
              <option key={z.id} value={z.id}>
                {formatOffset(z.offset)} · {z.label}
              </option>
            ))}
          </select>
        ) : (
          <>
            {zoneDisplay(tz)}
            <button onClick={onTzEdit}>{copy.change}</button>
          </>
        )}
      </div>
    </section>
  );
}
