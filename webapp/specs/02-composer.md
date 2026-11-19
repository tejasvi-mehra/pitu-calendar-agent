# 02 — Composer: mic, send, timezone

Inherits `00-foundation.md`. The bottom bar: how a request enters the app.

Owns: `src/components/Composer.tsx`, `src/components/MicButton.tsx`.

---

## 1. Layout

Sticky to the bottom of the page, full width of the content column.

```
┌───────────────────────────────────────────────┐
│  ▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁   ← 2px progress, only while busy
│  ( 🎤 )  ┌────────────────────────┐   [ → ]   │
│          │ Type or speak…         │           │
│          └────────────────────────┘           │
│             Asia/Hong_Kong · change           │
└───────────────────────────────────────────────┘
```

```css
.composer {
  position: sticky; bottom: 0;
  background: var(--paper);
  border-top: 1px solid var(--line);
  padding: var(--space-2) var(--space-3);
  padding-bottom: max(var(--space-2), env(safe-area-inset-bottom));
  display: grid;
  grid-template-columns: auto 1fr auto;
  gap: var(--space-2);
  align-items: end;
}
```

- No floating rounded container. The bar is flush to the page edges of the content
  column, separated by one 1px line.
- The timezone line sits below the row, `--ink-soft`, 12px.

## 2. Mic button

Round, accent, the only pulse in the app.

```css
.mic {
  width: 52px; height: 52px; border-radius: 50%;
  border: 0; background: var(--accent); color: var(--accent-ink);
  display: grid; place-items: center;
  cursor: pointer;
  transition: transform 160ms ease, background 160ms ease;
}
.mic:active { transform: scale(0.96); }
.mic[aria-pressed="true"] {
  background: var(--clay);
  animation: pulse 1.2s ease-out infinite;
}
@keyframes pulse {
  0%   { box-shadow: 0 0 0 0   rgb(163 59 43 / 0.45); }
  70%  { box-shadow: 0 0 0 14px rgb(163 59 43 / 0); }
  100% { box-shadow: 0 0 0 0   rgb(163 59 43 / 0); }
}
@media (prefers-reduced-motion: reduce) {
  .mic[aria-pressed="true"] { animation: none; box-shadow: 0 0 0 4px var(--paper-2) inset; }
}
```

- Icon: 22px mic glyph, stroke `--accent-ink`, 2px.
- `aria-label` is `Start voice input` / `Stop voice input`; `aria-pressed` mirrors state.
- The pulse ring is the **only** looping animation; it exists only while listening.
- When speech is unsupported, the mic is **not rendered at all** (not disabled), and the
  grid becomes two columns.

## 3. Text field

```css
.composer textarea {
  width: 100%; resize: none;
  background: var(--paper-2);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  padding: 14px var(--space-3);
  color: var(--ink); font: 400 16px/1.45 inherit;
  min-height: 52px; max-height: 132px;      /* grows to 4 rows, then scrolls */
}
.composer textarea:focus {
  outline: 2px solid var(--accent); outline-offset: 2px;
}
```

- Placeholder: `Type or speak…` (`--ink-soft`).
- Auto-grows with content up to 132px, then scrolls internally.
- `Enter` sends; `Shift+Enter` inserts a newline. On mobile the send button is the
  primary path and `Enter` behaviour is untouched.
- Speech interim text **replaces** the field's content while speaking, and is editable
  after speech ends.

## 4. Send button

Round, 44px, `--ink` fill while enabled.

```css
.send {
  width: 44px; height: 44px; border-radius: 50%;
  border: 0; background: var(--ink); color: var(--paper);
  display: grid; place-items: center;
}
.send:disabled { background: var(--line); color: var(--ink-soft); cursor: default; }
```

- Icon: 18px arrow, 2px stroke.
- Disabled when the field is empty, busy, or signed out.
- No label text. `aria-label="Send"`.

## 5. Busy state

A 2px bar at the top edge of the composer, spanning the content width, in `--accent`.

```css
.progress {
  position: absolute; top: -1px; left: 0; right: 0; height: 2px;
  background: var(--accent);
  animation: sweep 1.1s ease-in-out infinite;
  transform-origin: left;
}
@keyframes sweep { 0% { transform: scaleX(0.05); } 50% { transform: scaleX(0.7); } 100% { transform: scaleX(0.05); } }
```

- No spinner, no overlay, no dimming of the page.
- The send button becomes disabled and the textarea stays editable during `busy`.
- This animation is state, not decoration; it is allowed like the pulse.

## 6. Timezone

```css
.tz { font: 400 12px/1.3 inherit; color: var(--ink-soft); grid-column: 1 / -1; }
.tz button { background: none; border: 0; color: var(--ink-soft); text-decoration: underline; padding: 0 0 0 4px; font: inherit; }
```

- Default text: `Asia/Hong_Kong` — the resolved zone, shown as-is, no parentheses.
- Appended `· change` opens a `<select>` in place of the line (same width, one row).
- Options: device zone, `Asia/Singapore`, `Europe/London`, `America/New_York`, `UTC`.
- Choosing a value calls `resolveTimezone` and sends it as `X-Timezone` on the next
  request. No page reload.
- The picker is a real `<select>` styled with `appearance: none` and a custom 16px
  chevron positioned inside the padding — the native arrow must never sit outside the
  border, on any OS.

## 7. Speech behaviour

| Event | Result |
|---|---|
| Tap mic | `listen(onFinal, onEnd)`; interim results fill the field |
| Tap again, or recognition ends | stop; the field keeps the transcript |
| Speech unsupported | mic not rendered; a 12px `--ink-soft` line reads `Type your request` |
| Permission denied | one inline `--clay` line: `Microphone access was denied.` Mic returns to idle |

## 8. Acceptance

1. At 375px: mic (52px), field, send (44px) share one row without overflow; the bar
   clears the home-indicator safe area.
2. Listening: exactly one pulse ring loops; all other motion is ≤ 250 ms.
3. `prefers-reduced-motion`: no pulse, a static inset ring instead.
4. Tap mic, speak, tap stop: transcript is editable and appears in the field.
5. Empty field: send disabled. One character: send enabled.
6. Send: progress bar sweeps; no spinner anywhere; field stays editable.
7. Enter sends; Shift+Enter adds a line; field stops growing at 132px.
8. Timezone line reads the device zone with no parentheses; `change` swaps it for a
   select without shifting layout height by more than 2px.
9. The select's chevron is inside the border in both light and dark mode.
10. No gradient, no glow, no blue/violet in `Composer.tsx` or `MicButton.tsx`.
11. Keyboard-only: mic → field → send → timezone, in that order, with visible focus.
12. `aria-pressed` on the mic matches the listening state at all times.
