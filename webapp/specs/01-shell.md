# 01 — Page shell, header and account chip

Inherits `00-foundation.md`. This is the frame every other page renders inside.

Owns: `src/App.tsx`, `src/components/Header.tsx`, `src/components/AccountChip.tsx`,
`src/lib/copy.ts`.

---

## 1. Layout

Three regions, one column.

```
┌───────────────────────────────────────────┐
│  Pitu                        ( T ⌄ )      │  header   56px, sticky top
├───────────────────────────────────────────┤
│                                           │
│            <History />                    │  flex: 1, scrolls
│                                           │
├───────────────────────────────────────────┤
│            <Composer />                   │  sticky bottom, safe-area aware
└───────────────────────────────────────────┘
```

```css
.app {
  max-width: 620px; margin: 0 auto;
  min-height: 100dvh;
  display: grid;
  grid-template-rows: auto 1fr auto;
  background: var(--paper);
  color: var(--ink);
}
```

- Page background is `--paper`; no decorative layer, no gradient, no texture image.
- Header sits on `--paper` with a single 1px `--line` bottom border. It does not float,
  does not blur, does not change on scroll.
- The `<main>` scroll container is the middle row only. Header and composer never scroll.

## 2. Header

```css
.header {
  position: sticky; top: 0; z-index: 10;
  height: 56px; padding: 0 var(--space-3);
  display: flex; align-items: center; justify-content: space-between;
  background: var(--paper);
  border-bottom: 1px solid var(--line);
}
.wordmark { font-size: 20px; font-weight: 700; letter-spacing: -0.01em; }
```

- Wordmark is the literal text `Pitu`. It is not an image, not a logo mark, and no word
  inside it is set in a different face.
- No tagline, no version string, no status dot.

## 3. Account chip

Top right. The only affordance in the header besides the wordmark.

### Signed out

```
[ Sign in with Google ]
```
```css
.chip-signedout {
  border: 1px solid var(--accent);
  color: var(--accent);
  background: transparent;
  border-radius: var(--radius-pill);
  padding: 8px 16px; min-height: 36px;
  font: 600 14px/1 inherit;
}
```

### Signed in

```
( T ) ⌄
```
```css
.chip {
  display: inline-flex; align-items: center; gap: 8px;
  background: transparent; border: 0; padding: 4px;
  min-height: 44px; min-width: 44px;
}
.avatar {
  width: 32px; height: 32px; border-radius: 50%;
  background: var(--accent); color: var(--accent-ink);
  display: grid; place-items: center;
  font: 600 14px/1 inherit;
}
.chevron { width: 16px; height: 16px; color: var(--ink-soft); }
```

- Avatar shows the first letter of the email, uppercased. **No photo placeholder, no
  initials ring, no gradient fill.**
- If the email is unknown, the avatar shows `•` and the popover shows only `Sign out`.
- Chevron is a 16px inline SVG stroke in `--ink-soft`.

### Popover

Opens below the chip, right-aligned, 8px gap.

```css
.popover {
  position: absolute; top: calc(100% + 8px); right: 0;
  min-width: 220px;
  background: var(--paper-2);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  padding: var(--space-2);
  box-shadow: 0 4px 16px rgb(28 27 25 / 0.08);   /* the only real shadow in the app */
  z-index: 20;
}
.popover-email { font: 13px/1.3 inherit; color: var(--ink-soft); padding: 4px 8px; }
.popover-action { width: 100%; text-align: left; padding: 10px 8px; border: 0;
                  background: transparent; color: var(--ink); font: 15px/1.2 inherit; }
.popover-action:hover { background: var(--paper); border-radius: 8px; }
```

- Contents: the email line (if known), a 1px `--line` divider, then `Sign out`.
- No icons in the popover. No second action.
- Closes on outside click, on `Escape`, and on selection.
- Focus moves to `Sign out` when opened by keyboard; focus returns to the chip on close.

## 4. App state ownership

`App.tsx` holds exactly this:

```ts
token: string | null          // from lib/auth
email: string | null          // from localStorage 'pitu.email', set after first 200
history: Turn[]               // { role: 'user'|'assistant', text: string, at: number }
busy: boolean                 // a request is in flight
error: string | null          // inline error for the latest turn
override: string              // timezone override, '' = device
speakNext: boolean            // read-aloud preference, default false
```

- No state library. No context. Props only.
- `speakNext` starts `false` and is user-turned-on only (see `03-history.md`).
- History starts empty on every load; it is never persisted.

## 5. Sign-in flow

1. `Sign in with Google` calls `signIn(CLIENT_ID)` from `lib/auth.ts`.
2. On success: keep the token in the module variable (never `localStorage`), fire one
   `GET /health` to confirm reachability, then set `token`.
3. Store the email only if the server returns it; otherwise leave `email` null.
4. On failure: inline `--clay` text under the button, one sentence, no toast:
   *"Sign-in was cancelled. Try again."* or *"Google did not respond. Try again."*

## 6. Sign-out flow

1. `signOut()` from `lib/auth.ts` revokes the GIS token.
2. Clear `token`, `history`, `error`, `speakNext`.
3. Keep the timezone override; it is a device preference, not account data.
4. Header returns to the signed-out chip. No confirmation dialog.

## 7. States

| State | Rendering |
|---|---|
| Signed out | Header chip = sign-in button. Body shows the signed-out panel (§8). Composer hidden |
| Signed in, empty history | History empty state (`03-history.md`), composer visible |
| Signed in, error | Inline error in the history area, header unchanged |
| Loading | No skeleton, no spinner. Send control shows a 2px progress line (`02-composer.md`) |

## 8. Signed-out panel

Replaces history and composer. Centred in the middle row, max 380px.

```
Pitu

Schedule, move and cancel events by voice or text.
Sign in with Google to start.
```

- One paragraph, two sentences maximum.
- The sign-in control here duplicates the header chip's behaviour but is the primary
  accent-filled button on the page — the only filled button while signed out.
- No feature list, no three-item benefit block, no screenshot.

## 9. Copy (`lib/copy.ts`)

```ts
export const copy = {
  wordmark: "Pitu",
  signIn: "Sign in with Google",
  signOut: "Sign out",
  signedOutBody: "Schedule, move and cancel events by voice or text. Sign in with Google to start.",
  signInCancelled: "Sign-in was cancelled. Try again.",
  signInFailed: "Google did not respond. Try again.",
  sessionExpired: "Session expired. Sign in again.",
  genericError: "Pitu could not finish that. Try again.",
  offline: "Cannot reach Pitu. Check your connection.",
};
```

Strings are referenced from `copy`, never written inline in JSX.

## 10. Acceptance

1. At 375px width the header is 56px, the wordmark is left, the chip is right, and both
   clear the safe area.
2. No element on the page uses a gradient, a blue, or a violet.
3. Signed out: exactly one filled accent button exists, in the signed-out panel; the
   header chip is accent-outlined.
4. Sign-in: the chip becomes a 32px letter avatar with a chevron; no photo loads.
5. Popover: opens on click, closes on outside click and on `Escape`, focus returns to
   the chip, contains the email when known and `Sign out`, nothing else.
6. `Sign out` clears history and returns to the signed-out panel without a dialog.
7. Dark mode: background is warm charcoal, accent is unchanged in hue, no navy.
8. Keyboard: `Tab` reaches wordmark area → chip → sign-in; focus ring is visible on all.
9. Nothing in the header animates on scroll.
10. `grep -rnE '#(6366f1|8b5cf6|a855f7|3b82f6|0f172a)' webapp/src` returns nothing.
