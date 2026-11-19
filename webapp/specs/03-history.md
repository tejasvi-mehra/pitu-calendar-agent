# 03 — Chat history and read-aloud

Inherits `00-foundation.md`. The scrolling middle region: every exchange, plus the
per-message voice control.

Owns: `src/components/History.tsx`, `src/components/Turn.tsx`.

---

## 1. Layout

```
┌───────────────────────────────────────────┐
│  you                                      │  label, --ink-soft, 13px
│  book lunch tomorrow 1pm                  │  text, --ink, 16px
│                                           │
│  Pitu                       12:04         │  label + time, right-aligned time
│  Booked for tomorrow at 13:00.            │
│  ⏵ Read aloud                             │  control, only on assistant turns
│  ─────────────────────────────────────────│  1px --line separator between turns
│  you                                      │
│  cancel my CV update meeting              │
│                                           │
│  Pitu                       12:07         │
│  Deleted the one without guests.          │
│  ⏵ Read aloud                             │
└───────────────────────────────────────────┘
```

```css
.history {
  overflow-y: auto;
  padding: var(--space-3);
  display: flex; flex-direction: column;
  gap: var(--space-4);
  scroll-behavior: auto;            /* never smooth: it fights scroll lock */
}
.turn { display: grid; gap: 6px; }
.turn + .turn { border-top: 1px solid var(--line); padding-top: var(--space-4); }
.label { font: 500 13px/1.3 inherit; color: var(--ink-soft); display: flex; justify-content: space-between; }
.time  { color: var(--ink-soft); font-variant-numeric: tabular-nums; }
.text  { font: 400 16px/1.55 inherit; color: var(--ink); white-space: pre-wrap; word-break: break-word; }
```

- **No bubbles.** Turns are separated by a hairline, not by rounded containers.
- No avatars in the list. The account chip in the header is the only identity marker.
- User and assistant text use the same type; only the label differs. This is deliberate
  — two bubble styles is the default chat template.
- No max-width off-centre alignment: everything is left-aligned to one gutter.

## 2. Auto-scroll rule

```
if user is within 64px of the bottom -> scroll to bottom on append
otherwise -> do not move; show a small "↓" control pinned bottom-right of the list
```

```css
.jump {
  position: sticky; bottom: 0; align-self: flex-end;
  width: 32px; height: 32px; border-radius: 50%;
  background: var(--paper-2); border: 1px solid var(--line); color: var(--ink);
}
```

- The jump control appears only when locked and unread content exists below.
- It disappears on tap and on reaching the bottom.

## 3. Read-aloud

Voice output is **off by default**. There is no global "speak everything" switch.

```css
.read {
  justify-self: start;
  display: inline-flex; align-items: center; gap: 6px;
  border: 0; background: transparent; padding: 0;
  color: var(--ink-soft); font: 500 13px/1.3 inherit;
  min-height: 44px;
}
.read:hover { color: var(--ink); }
```

| State | Label | Behaviour |
|---|---|---|
| Idle | `Read aloud` | speaks this turn only |
| Speaking | `Stop` | cancels synthesis immediately |
| After speaking once | `Read aloud` | can be replayed |

- A turn is spoken with the user's chosen voice (`localStorage 'pitu.voice'`), or the
  system default.
- Only one turn speaks at a time. Starting another cancels the first.
- If the user taps `Read aloud` on a new turn, the **next** reply also speaks once, then
  the preference resets. This gives continuity without a hidden global mode.
- The control is absent on user turns.

## 4. States

| State | Rendering |
|---|---|
| Empty (signed in) | Centred, max 340px: `Ask Pitu to book, move or cancel something.` and one example line in `--ink-soft`: `Try “book a 30 min meeting tomorrow at 4pm”.` No illustration |
| Busy | No skeleton. The last assistant turn keeps its text; the composer shows progress |
| Error | Assistant turn replaced by `--clay` text and a `Retry` text button inline beneath |
| Session expired | One `--clay` line: `Session expired. Sign in again.` with the sign-in control inline; history preserved |
| Long reply | Wraps; no truncation, no "show more" |

Error block:

```css
.error { color: var(--clay); display: grid; gap: 8px; justify-items: start; }
.error .retry { border: 0; background: transparent; color: var(--clay); text-decoration: underline; font: 500 14px/1.2 inherit; min-height: 44px; }
```

- Errors never use a toast, a banner, or a modal.

## 5. Announcements

- One polite live region, visually hidden, updated **once** per completed assistant turn
  with the turn's text.
- User turns are not announced (the user wrote or spoke them).

```html
<p class="sr-only" role="status" aria-live="polite">{lastAssistantText}</p>
```

## 6. Data shape

```ts
type Turn = { role: "user" | "assistant"; text: string; at: number };
```

- `at` is `Date.now()`; the time label renders `HH:mm` in the user's locale.
- History is capped in memory at 50 turns; the oldest is dropped silently.
- Nothing is persisted. Reload clears the list.

## 7. Acceptance

1. Two exchanges render as four turns separated by hairlines, with no bubbles and no
   avatars.
2. The reply is **silent** on arrival; audio only after `Read aloud` is tapped.
3. `Read aloud` → `Stop` stops mid-sentence within 200ms.
4. Starting `Read aloud` on a second turn cancels the first.
5. Scroll up 500px, send a message: the view does not jump; a `↓` control appears and
   returns to the newest turn when tapped.
6. At the bottom, a new turn scrolls into view automatically.
7. Server stopped, then send: inline `--clay` error with `Retry`; history intact; no
   toast.
8. Empty state shows one sentence and one example; no images.
9. A 300-word reply wraps fully with no truncation.
10. Screen reader announces each completed assistant turn exactly once.
11. Dark mode: hairline is `--line`, labels stay `--ink-soft` at ≥ 4.5:1.
12. No gradient, no bubble radius, no blue/violet in `History.tsx` or `Turn.tsx`.
