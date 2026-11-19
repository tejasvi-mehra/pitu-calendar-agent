# SPEC — Pitu web client

Status: draft 1, not implemented. Backend contract is fixed by `../SPEC.md` §4–6; this
file governs only `webapp/`.

Scope: everything the browser renders and does. It does not change the API, the MCP
server, or the agent.

---

## 1. What this client is for

One person, one thumb, one phone. They open the page, sign in with Google once, say or
type a request, and read the reply in a running history. Nothing else.

The client is a thin shell over `POST /chat`. Every decision an agent makes lives on
the server; the client must not invent, cache, or re-derive any of it.

## 2. Design direction

**Look:** warm paper, ink, and one loud accent. Explicitly *not* the default
AI-product look.

| Decision | Value | Why |
|---|---|---|
| Default theme | Light, warm off-white | Dark navy is the default of every agent demo |
| Accent | Terracotta `#C2532E` | Warm, uncommon in AI products |
| Secondary | Sage `#5B7B6A` | Lets state be carried by a second hue, not by more blue |
| Headline type | Same family as body, one weight heavier | Avoids the "one word in serif" tell |
| Surfaces | One background, separators between blocks | No cards inside cards |
| Motion | Only while something is actually happening | No hover glow, no decorative transitions |

### 2.1 Tokens

```css
:root {
  --paper:      #FAF7F2;  /* app background */
  --paper-2:    #F1ECE3;  /* composer, hover */
  --ink:        #1C1B19;  /* primary text */
  --ink-soft:   #6B665E;  /* secondary text, timestamps */
  --line:       #E2DACD;  /* separators, borders */
  --accent:     #C2532E;  /* primary action, mic */
  --accent-ink: #FFF8F4;  /* text on accent */
  --sage:       #5B7B6A;  /* success, "booked" */
  --clay:       #A33B2B;  /* error */
  --radius:     14px;
  --radius-pill: 999px;
}
```

Dark mode is defined under `prefers-color-scheme: dark` with warm charcoal
(`#171614`), never navy, and the same accent hue.

**Hard prohibitions in code review:**

- no `linear-gradient` on any button, header or card
- no `box-shadow` used as a glow; shadows only for the composer when it has focus
- no `#6366f1`, `#8b5cf6`, `#3b82f6`, `#0f172a` or any indigo/blue/close-to-it token
- maximum one accent element per screen region
- no animation longer than 250 ms except the listening pulse

## 3. Layout

Single column, `max-width: 620px`, centred. Two fixed regions and one scrolling one.

```
┌─────────────────────────────────────────┐
│  Pitu                      [ (T) ⌄ ]    │  header, sticky, 56px
├─────────────────────────────────────────┤
│                                         │
│  you        book lunch tomorrow 1pm     │  history, scrolls
│  Pitu       Booked for 13:00 tomorrow.  │
│             [ 🔊 read aloud ]           │
│                                         │
│  you        cancel CV update meeting    │
│  Pitu       Deleted the one with no     │
│             guests.                     │
│                                         │
├─────────────────────────────────────────┤
│  [ 🎤 ]  ┌──────────────────────┐ [→]  │  composer, sticky bottom
│          │ Type or speak…       │       │
│          └──────────────────────┘       │
└─────────────────────────────────────────┘
```

- Header: wordmark left, account chip right. Sticky.
- History: newest at the bottom, auto-scrolled to bottom on new message, but **not**
  if the user has scrolled up.
- Composer: sticky, respects `env(safe-area-inset-bottom)`. Text field grows to 4 rows
  then scrolls.
- Empty state: one line of guidance and three example phrasings. No illustration.

## 4. Account chip

Top right. Mirrors the familiar Google account control, at this app's scale.

| State | Rendering |
|---|---|
| Signed out | `Sign in with Google` button, accent outline |
| Signed in | Circle avatar (first letter of the email, `--accent` background, `--accent-ink` text), chevron |
| Open | Small popover: full email, `Sign out` |

- Avatar is **initial-based**. GIS gives no profile photo without the `profile` scope,
  which this app does not request. Do not add a photo placeholder.
- The email is available only from `tokeninfo` on the server. The client gets it from
  `localStorage` after a successful `GET /me`, or decodes it from a verified response —
  until Phase 6 adds `/me`, the chip shows the initial plus "Signed in" and opens a
  popover with just `Sign out`.
- `Sign out` revokes the GIS token and clears history.

## 5. Chat history

- One array in memory: `{ role: 'user' | 'assistant', text, at }`.
- User turns: right-aligned-free but visually distinct — `--ink-soft` label above, text
  in `--ink`.
- Assistant turns: label `Pitu`, text in `--ink`, plus a `Read aloud` control.
- History is **not** persisted. Reload clears it. Server-side persistence is out of
  scope for this client.
- Failure: the assistant turn is replaced by an inline error in `--clay` with a
  `Retry` action. Never a toast.
- Session expiry (401): one inline line, "Session expired. Sign in again." with the
  sign-in control, history preserved.

## 6. Composer and voice

| Element | Behaviour |
|---|---|
| Mic button | Round, 52px, `--accent` fill. Tap to start, tap to stop |
| Listening | Pulsing ring: `box-shadow` ripple or `scale` 1 → 1.06, 1.2 s loop |
| Speech unsupported | Mic hidden, not disabled. Text field is the only input |
| Transcript | Interim speech inserts into the text field, editable before send |
| Send | Icon button, `--ink`, disabled when empty or busy |
| Busy | Send becomes a thin progress line above the composer, no spinner overlay |

**Voice output is off by default.** There is no global "speak replies" switch binding
the whole app. Each assistant turn carries a `Read aloud` toggle; when a user turns it
on for one message, the next reply also speaks, and the setting can be turned off again
at any time. A `Stop` control appears while audio plays.

- `prefers-reduced-motion: reduce` disables the pulse, keeps the state colour.
- Pulse is the only looping animation in the app.

## 7. Copy rules

- Sentences, not fragments. No exclamation marks.
- Never show an event id, a model name, a token, a tool name, or JSON.
- Empty state, error, and loading strings are written once in `copy.ts`, not inline.

## 8. Accessibility

- Every control reachable by keyboard; mic and send are real `<button>`s.
- Listening state announced with `aria-pressed` and a visually hidden live region.
- New replies announced once via a polite live region, not on every streamed token.
- Contrast: `--ink` on `--paper` ≥ 7:1; `--accent-ink` on `--accent` ≥ 4.5:1.
- Focus ring is a 2px `--accent` outline offset 2px, always visible.

## 9. Component map

| File | Responsibility |
|---|---|
| `src/App.tsx` | state, fetch, history array |
| `components/Header.tsx` | wordmark + `AccountChip` |
| `components/AccountChip.tsx` | avatar, popover, sign out |
| `components/History.tsx` | list, auto-scroll rule, empty state |
| `components/Turn.tsx` | one message, `ReadAloud` for assistant turns |
| `components/Composer.tsx` | mic, textarea, send |
| `components/MicButton.tsx` | round button + pulse |
| `lib/auth.ts` | GIS token client, module-variable token |
| `lib/speech.ts` | recognition, synthesis, voice list, stop |
| `lib/timezone.ts` | `resolveTimezone()` (unchanged) |
| `lib/copy.ts` | all user-facing strings |

Deleted from the current build: `SignIn.tsx` (folded into `AccountChip`),
`Transcript.tsx`, `Reply.tsx`.

## 10. Anti-pattern checklist

Reject any change that introduces:

| Tell | Check |
|---|---|
| Indigo/violet gradients | `grep -rnE '#(6366f1\|8b5cf6\|a855f7\|3b82f6\|0f172a)' webapp/src` → empty |
| Gradient on a control | `grep -rn 'linear-gradient' webapp/src` → empty |
| Glow shadows | `grep -rn 'box-shadow' webapp/src` → only composer focus |
| Nested cards | no `.card` inside `.card`; separators only |
| Uniform three-item blocks | no list of exactly three bullets repeated per section |
| Arbitrary numerals | no `01 / 02 / 03` styling anywhere |
| Decorative motion | only the listening pulse and a ≤250 ms message entrance |
| Inter as the only face | body uses the platform stack; no webfont load at all |
| Big empty space | vertical rhythm is content-driven; no fixed spacer taller than 32px |
| Stock illustrations or emoji sets | none; emoji allowed only on the mic and stop controls |

## 11. Acceptance

Manual, phone-width first (375px), then desktop.

1. Fresh load: paper background, terracotta mic, no blue or purple on screen.
2. Signed out: header shows `Sign in with Google`; sign-in brings back an avatar chip.
3. Tap mic: ring pulses; tap again: it stops. Nothing else on the page animates.
4. Ask "book lunch tomorrow 1pm": user turn appears, then the reply; the reply is
   **silent** by default.
5. Tap `Read aloud` on that reply: it speaks. Tap `Stop`: it stops mid-sentence.
6. Ask two more things: history shows all three exchanges, scrolls to the newest.
7. Scroll up, send again: the view does **not** jump to the bottom.
8. Kill the server, send: inline error with `Retry`, no toast, no lost history.
9. Expire the token (wait an hour or revoke), send: one-line re-auth prompt, history
   intact.
10. Open the account chip → `Sign out` → history gone, signed-out button back.

Automated where cheap:

- Vitest: `resolveTimezone`, `copy` completeness, history reducer (append, error,
  scroll-lock).
- One Playwright smoke: sign-in mock → send → reply rendered → history length 2.

## 12. Build and run

```
npm --prefix webapp install
npm --prefix webapp run build     # -> webapp/dist, served by FastAPI at /
npm --prefix webapp run dev       # :5173, proxies /chat and /health to :8000
npm --prefix webapp run test
```

`VITE_GOOGLE_CLIENT_ID` comes from `webapp/.env` (gitignored). No other environment
variables reach the client.

## 13. Out of scope for this file

Server behaviour, approval flow, retrieval, and evaluation are specified in
`../SPEC.md`. Nothing here changes them.

## 14. Change log

- Draft 1 — warm paper/terracotta palette replacing the navy/blue default; round
  pulsing mic; account chip in the header; persistent chat history with per-message
  read-aloud; explicit anti-AI-slop checklist.
