# 00 — Shared design contract

Read this before any page spec. Every page inherits it; none may override it.

---

## 1. Product

Pitu is a voice-and-text calendar agent. One person, one thumb, one phone. The
browser is a thin shell over `POST /chat` — every decision lives on the server.

## 2. Non-negotiable prohibitions

These exist because they are the tells of a default AI-generated interface. A page
fails review on any one of them.

| Prohibited | Reason |
|---|---|
| Indigo / violet / blue accent (`#6366f1`, `#8b5cf6`, `#a855f7`, `#3b82f6`, `#0f172a`) | the default of every agent demo |
| `linear-gradient` on any control, header or card | gloss is the tell |
| Glow (`box-shadow` with blur as decoration) | shadows only on the focused composer |
| Cards nested inside cards | one surface per region |
| Lists of exactly three items repeated per section | formulaic rhythm |
| `01 / 02 / 03` decorative numbering | arbitrary numbering |
| A webfont, especially Inter alone | platform stack only, zero font requests |
| "One word highlighted in serif" inside a sans headline | classic tell |
| Hover glow, parallax, or any motion that is not state | motion means something is happening |
| Empty vertical space taller than 32px used for rhythm | spacing is content-driven |
| Stock illustrations, 3D blobs, abstract tech shapes | none |
| Emoji beyond the mic and stop controls | none |

## 3. Tokens

Every page uses these names and no others.

```css
:root {
  --paper:       #FAF7F2;
  --paper-2:     #F1ECE3;
  --ink:         #1C1B19;
  --ink-soft:    #6B665E;
  --line:        #E2DACD;
  --accent:      #C2532E;
  --accent-ink:  #FFF8F4;
  --sage:        #5B7B6A;
  --clay:        #A33B2B;
  --radius:      14px;
  --radius-pill: 999px;
  --space-1: 8px; --space-2: 12px; --space-3: 16px; --space-4: 24px; --space-5: 32px;
}

@media (prefers-color-scheme: dark) {
  :root {
    --paper:      #171614;
    --paper-2:    #201E1B;
    --ink:        #F2EDE6;
    --ink-soft:   #9A948B;
    --line:       #322E29;
    --accent:     #D9704A;
    --accent-ink: #1A0F0A;
    --sage:       #7FA08C;
    --clay:       #D2705E;
  }
}
```

## 4. Type

Platform stack only. No font loading.

```css
font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
```

| Role | Size / weight / line-height |
|---|---|
| Wordmark | 20px / 700 / 1.1, letter-spacing -0.01em |
| Body | 16px / 400 / 1.55 |
| Message text | 16px / 400 / 1.55 |
| Label (`you`, `Pitu`, timestamp) | 13px / 500 / 1.3, `--ink-soft` |
| Button | 15px / 600 / 1.2 |

## 5. Space and radius

- Page gutter: 16px (12px below 400px width).
- Max content width: 620px, centred.
- Vertical rhythm: `--space-2` between related items, `--space-4` between turns.
- Radius: `--radius` on inputs and popovers, `--radius-pill` on the mic and send.
- Borders: 1px `--line`. Never a border and a shadow on the same element.

## 6. Motion

- The **only** looping animation in the app is the mic listening pulse.
- Every other transition is ≤ 250 ms and happens on a state change only.
- `prefers-reduced-motion: reduce` removes the pulse's scale, keeps a static ring.

## 7. Accessibility floor

- Contrast: `--ink` on `--paper` ≥ 7:1; `--accent-ink` on `--accent` ≥ 4.5:1.
- Focus ring: 2px `--accent`, offset 2px, never removed.
- Touch targets ≥ 44×44px.
- Every interactive element is a real `<button>`, `<a>`, `<input>`, or `<select>`.
- New assistant replies are announced once through a polite live region — not per
  streamed token.

## 8. Copy

- Sentences, not fragments. No exclamation marks. No em dash chains.
- Never render an event id, model name, token, tool name, or raw JSON.
- All user-facing strings live in `lib/copy.ts`.
- The product name is written `Pitu`.

## 9. Response contract (do not change)

```
POST /chat          Authorization: Bearer <google access token>
                    X-Timezone: <IANA zone>
                    {"text": "..."}
            -> 200 {"session": "...", "tz": "...", "reply": "..."}
            -> 401 {"detail": "..."}   401 = re-auth
            -> 403 / 429 / 502 {"detail": "..."}   generic, no internals
GET  /health        -> 200 {"ok": true}
```

The client issues requests exactly as above and renders `reply` as plain text.

## 10. File boundaries

Each page spec names only the files it owns. Shared files (`lib/*`) are fixed here
and edited by nobody except the session that owns them.

| Shared file | Owner | Contract |
|---|---|---|
| `lib/auth.ts` | 01 | exports `signIn`, `getToken`, `signOut`, `loadGis` |
| `lib/speech.ts` | 03 | exports `listen`, `speak`, `stopSpeaking`, `voices`, `speechSupported` |
| `lib/timezone.ts` | 02 | exports `resolveTimezone`, `detectBrowserZone` |
| `lib/copy.ts` | 01 | every user-facing string |

## 11. Page index

| Spec | Surface | Owns |
|---|---|---|
| `01-shell.md` | header, account chip, page frame | `App.tsx`, `Header.tsx`, `AccountChip.tsx` |
| `02-composer.md` | bottom input bar, mic, send, timezone | `Composer.tsx`, `MicButton.tsx` |
| `03-history.md` | message list, read-aloud, states | `History.tsx`, `Turn.tsx` |

Each page spec is self-contained: layout, states, exact CSS, and its own acceptance
list. Generate one page per session; do not let one session touch another's files.
