import { useEffect, useRef, useState } from "react";
import { copy } from "../lib/copy";
import { voices } from "../lib/speech";

export function AccountChip({
  email,
  voice,
  onVoice,
  onSignIn,
  onSignOut,
}: {
  email: string | null;
  voice: string;
  onVoice: (name: string) => void;
  onSignIn: () => void;
  onSignOut: () => void;
}) {
  const [open, setOpen] = useState(false);
  const wrap = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const action = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!open) return;
    action.current?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setOpen(false);
        trigger.current?.focus();
      }
    };
    const onClick = (e: MouseEvent) => {
      if (!wrap.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("keydown", onKey);
    document.addEventListener("mousedown", onClick);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("mousedown", onClick);
    };
  }, [open]);

  if (!email) {
    return (
      <button className="chip-signedout" onClick={onSignIn}>
        {copy.signIn}
      </button>
    );
  }

  return (
    <div className="chip-wrap" ref={wrap}>
      <button
        ref={trigger}
        className="chip"
        aria-expanded={open}
        aria-haspopup="menu"
        aria-label={email}
        onClick={() => setOpen((v) => !v)}
      >
        <span className="avatar" aria-hidden="true">
          {email.charAt(0) || "•"}
        </span>
        <svg className="chevron" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
          <path d="M6 9l6 6 6-6" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </button>
      {open && (
        <div className="popover" role="menu">
          <div className="popover-email">{email}</div>
          <div className="popover-divider" />
          <label className="popover-field">
            <span>{copy.voice}</span>
            <select
              className="popover-select"
              value={voice}
              onChange={(e) => onVoice(e.target.value)}
            >
              <option value="">System default</option>
              {voices().map((v) => (
                <option key={v.name} value={v.name}>
                  {v.name} ({v.lang})
                </option>
              ))}
            </select>
          </label>
          <div className="popover-divider" />
          <button
            ref={action}
            className="popover-action"
            role="menuitem"
            onClick={() => {
              setOpen(false);
              onSignOut();
            }}
          >
            {copy.signOut}
          </button>
        </div>
      )}
    </div>
  );
}
