# SPEC — Pitu - Calendar Agent

Status: draft 5, awaiting approval. Nothing is implemented until this file is signed off.
Design diagrams: `docs/diagrams.md`.

---

## 1. Objective

A multi-user service where anyone signs in with their own Google account on a phone or laptop, speaks a request, and gets events booked on **their own** calendar. The server holds no Google credentials, and the model provider never sees a token.

One sentence for the CV: *an MCP-based calendar agent with retrieval grounding, human approval, per-user OAuth isolation, and a measured eval harness.*

## 2. Claims and evidence

Every claim on the CV must map to a file a reviewer can open.

| Claim | Evidence artifact |
|---|---|
| Agentic AI | agent loop with 3 tools, system prompt policy, streaming |
| Model Context Protocol | `mcp_server.py`, inspector transcript in `docs/proof/` |
| RAG | `retrieval.py`, notes agent, retrieval tests, cited-source answer in `docs/proof/` |
| Agentic harness | `traces/*.jsonl`, eval runner, guardrails, HITL approval |
| Multi-tenant OAuth | browser-held tokens, no server credential store, per-session MCP process |
| AI evals | `evals/cases.jsonl`, `evals/report.md` with pass rate and cost |
| Guardrails and governance | call budget, audit trace, redacted tokens, allowlist |
| Context engineering | system prompt + retrieved notes + injected clock and timezone |

## 3. Invariants

Conditions the system must never violate. Each is covered by a test from the phase that could break it; the full set is green at the publish gate.

| ID | Invariant | Enforced from |
|---|---|---|
| I1 | The Google access token never appears in any message sent to the model provider. | P2 |
| I2 | The access token never appears in logs, traces, or error responses. | P1 |
| I3 | The token is never a tool parameter in any tool schema. | P1 |
| I4 | At most one write tool call per user request. | P1 |
| I5 | A failure never reports success, and a failed call books nothing. | P1 |
| I6 | A pending approval can only be confirmed by the Google account that created it. | P5 |
| I7 | The client page loads no third-party script other than Google Identity Services. | P5 |
| I8 | Every route rejects a request that fails the audience, allowlist, or rate checks. | P4 |
| I9 | The timezone is validated against the IANA database; an unknown value falls back to the default and never raises. | P4 |
| I10 | The notes agent has no write tools and never receives a Google token. | P3 |

## 4. Architecture summary

Three trust zones; see `docs/diagrams.md` sections 1 and 3.

```
webapp (React, Vite) --HTTPS Bearer + X-Timezone--> FastAPI
   auth middleware (header, tokeninfo, aud, allowlist, rate limit)
   timezone resolve (IANA validated, else DEFAULT_TZ)
   -> calendar agent (messages only) -> OpenRouter  [MODEL]
   -> notes agent, read-only, called as a tool -> OpenRouter  [RESEARCH_MODEL]
   -> tool dispatch (token from request context)
      -> mcp_server subprocess per session (token in env)
         -> Google Calendar API
```

Repository layout at the publish gate:

```
server.py  mcp_server.py  retrieval.py  tools.py  pitu_agent.py  prompt.py
webapp/            React + Vite; source in webapp/src, built to webapp/dist
notes/             notes corpus
tests/  evals/  docs/proof/  traces/ (gitignored)
```

## 5. Environment contract

`.env.example` is committed; `.env` never is.

| Variable | Required | Purpose |
|---|---|---|
| `OPENROUTER_API_KEY` | yes | model access |
| `MODEL` | yes | OpenRouter model slug, must support tool calling |
| `OPENROUTER_BASE_URL` | no | default `https://openrouter.ai/api/v1` |
| `GOOGLE_CLIENT_ID` | from P1 | OAuth client id, public by design; Web type for P4–P5 |
| `GOOGLE_CREDENTIALS_PATH` | from P1 | path to the desktop OAuth client JSON used by `login.py`; lives outside the repo |
| `ALLOWED_EMAILS` | from P4 | comma-separated allowlist |
| `GOOGLE_TOKEN` | P1–P3 only | access token for CLI and MCP runs, never committed |
| `APP_PORT` | no | default 8000 |
| `RATE_LIMIT_PER_MIN` | no | default 10 |
| `DEFAULT_TZ` | no | fallback IANA zone, default `Asia/Singapore` |
| `RESEARCH_MODEL` | no | OpenRouter slug for the notes agent; defaults to `MODEL` |
| `NOTES_DIR` | no | default `notes/` |

Rules: no secret is read from a file path that can be committed. Missing required vars fail fast at startup with a named error.

## 6. Timezone

The user's zone comes from the client, never from the server's clock.

1. Client reads `Intl.DateTimeFormat().resolvedOptions().timeZone` — available in every browser without a permission prompt. The user can override it from a picker; the override wins.
2. Every `/chat` request sends it as `X-Timezone`.
3. Server validates with `ZoneInfo(name)`; on `InvalidKeyError` or a missing header it uses `DEFAULT_TZ`.
4. The resolved zone is passed into `make_calendar_tools(token, tz)` and used for `start`/`end` and `RRULE` `UNTIL`.

Before Phase 4 there is no client, so the zone comes from `DEFAULT_TZ`.

---

## 7. Phases

### Definition of each phase

Every phase from Phase 1 onward is a **vertical slice**: it ends with a real event created in a real Google Calendar, through the interface that phase adds.

A phase is not done until all five rows of its deliverable table are true:

| Deliverable | Requirement |
|---|---|
| Working booking | an event exists in the calendar, with the correct time in the correct zone |
| Trace | the run leaves an audit record; what it records grows per phase |
| Tests | new behaviour has a deterministic test; earlier tests still pass |
| Docs | the README gains the section for this phase |
| Evals | `evals/cases.jsonl` gains rows for what this phase makes possible; `run_evals.py` runs green |

Cross-cutting maturity, by phase:

| Deliverable | P1 | P2 | P3 | P4 | P5 |
|---|---|---|---|---|---|
| Trace | streamed node log | JSONL: tool, args, outcome, model slug | + retrieval step and cited files | + request id, auth outcome, resolved tz | + pending / approved / cancelled |
| Tests | pure fns, tool with fake service | MCP wiring, tool schema over the wire | retrieval, citation, no-notes path | routes, auth, I8/I9 | timezone helper, render escaping |
| Evals | contract runner, 6 cases | + 2 cases through MCP | + 3 citation cases | + 3 auth cases | + live layer run |
| Docs | README skeleton, arch diagram, run CLI | MCP section, inspector steps | notes and citations | API section with curl | UI, phone, tunnel |

Git tag each phase (`phase-0` … `phase-5`) so the history shows the slices.

---

### Phase 0 — Baseline and bug fixes

**Objective:** nothing leaks, nothing is broken on clone. No new capability.

| # | Fix |
|---|---|
| 0.1 | `.gitignore`: `.env`, `credentials.json`, `token.json`, `traces/`, `__pycache__/`, `node_modules/`, `webapp/dist/`, `.venv/`, `.DS_Store` |
| 0.2 | Delete `agents.py` (imports nonexistent `fetch_text_from_url`) |
| 0.3 | Delete `add_event.py` (superseded by eval cases) |
| 0.4 | Move `credentials.json` and `token.json` to `~/.config/calendar-agent/`; revoke the old token if it ever left the machine |
| 0.5 | Timezone: one definition in `tools.py` (`DEFAULT_TZ`) |
| 0.6 | Remove import-time side effects: model, agent, MCP client constructed inside functions only |
| 0.7 | Remove `get_google_creds` and the interactive `InstalledAppFlow` path from `tools.py`; server code builds the service from a bearer token. Token acquisition moves to `login.py` in Phase 1 |
| 0.8 | Write `docs/proof/before-after.md` with the measured baseline |

**Done when:** `grep -rn "InstalledAppFlow\|token.json\|credentials.json" *.py` returns nothing; `python -c "import pitu_agent"` exits 0 without network; `git status` shows no secret files.

**Try it yourself** (no model, no token):
```
.venv/bin/python -c "from tools import build_rrule; print(build_rrule('WEEKLY',2,0,'','MO,WE'))"
.venv/bin/python -c "from tools import add_calendar_event as t; print(sorted(t.args_schema.model_json_schema()['properties']))"
```
Expect `RRULE:FREQ=WEEKLY;INTERVAL=2;BYDAY=MO,WE` and a property list with **no** `token`.

---

### Phase 1 — Working booking from the CLI, on reusable pieces

**Objective:** book a real event from the command line, through an OpenRouter model, using the abstractions every later phase reuses.

#### Build

| Piece | File | Why it is shared later |
|---|---|---|
| `build_model()` | `pitu_agent.py` | the only place a chat model is constructed; P2–P5 all call it |
| `make_calendar_tools(token, tz)` | `tools.py` | binds credentials and zone to tools; P2 passes its output to MCP, P4 to the request |
| `build_agent(tools)` | `pitu_agent.py` | takes tools as a parameter; P2 hands it MCP-loaded tools instead |
| `require_token()` | `tools.py` | one place that reads `GOOGLE_TOKEN` and fails with a named error |
| `login.py` | new, standalone script | one-time OAuth: `InstalledAppFlow` (Desktop client) against `GOOGLE_CREDENTIALS_PATH`, writes `~/.config/calendar-agent/token.json`, prints the access token. Never imported by the server |

Entry point is a single script: `python pitu_agent.py "book …"`, or `python pitu_agent.py` for stdin input. No framework, no arguments beyond the request text.

- `ChatOpenAI` with `base_url`, `api_key`, and `Referer`/`X-Title` headers; `MODEL` slug in every trace line.
- `requirements.txt` pinned: `langchain==1.3.13`, `langchain-core==1.4.9`, `langgraph==1.2.9`, `langchain-openai`, `google-api-python-client==2.198.0`, `google-auth==2.56.0`, `google-auth-oauthlib==1.4.0` (for `login.py` only), `python-dotenv`, `pytest`.
- `langchain-ollama` removed from imports.
- Pure helpers stay importable and model-free: `parse_date_only`, `coerce_bool`, `build_rrule`.

#### Cross-cutting

| Deliverable | This phase |
|---|---|
| Trace | `traces/<session>.jsonl` created; node, tool, args, outcome, model slug, resolved tz. Tokens redacted (I2) |
| Tests | `test_tools.py`: date parsing, bool coercion, RRULE table, dedupe, failure returns `Failed`; `make_calendar_tools` against a monkeypatched service |
| Docs | `README.md`: what it is, architecture diagram, CLI quickstart, limitations stub |
| Evals | `evals/cases.jsonl` (6 rows), `evals/run_evals.py` contract layer, `evals/report.md` |

#### Done when

- `.venv/bin/python login.py` completes a Google consent and prints an access token; nothing credential-shaped is written inside the repo.
- `GOOGLE_TOKEN=… .venv/bin/python calendar_agent.py "book lunch with Priya tomorrow 1pm for 45 min"` prints `Created 'Lunch with Priya'` with an event id, and the event is visible in the calendar at the right time.
- A second identical request is refused by the write budget (I4), not attempted.
- `traces/*.jsonl` holds that run and `grep -c "ya29" traces/*.jsonl` is 0.
- `pytest` green; `run_evals.py` green.

#### Try it yourself

One-time setup: create a **Desktop** OAuth client in Google Cloud Console, save its JSON outside the repo, and point `GOOGLE_CREDENTIALS_PATH` at it. Then:
```
export GOOGLE_TOKEN=$(.venv/bin/python login.py --print-token)
.venv/bin/python calendar_agent.py "book a 30 min meeting tomorrow at 4pm"
.venv/bin/python calendar_agent.py "cancel it"                     # expect a plain reply, no tool
.venv/bin/python calendar_agent.py "book it for the 32nd of May"   # expect a Failed string, no retry
```
What to watch for: tool args containing `"4pm"` or `"tomorrow"` instead of concrete date/hour → tighten the prompt now. Note per-turn latency; that number decides whether `MODEL` stays. Tokens from `login.py` last about an hour, so a long debugging session needs a re-run — that is the same constraint the real client will have.

---

### Phase 2 — The same booking through an MCP server

**Objective:** the identical outcome, with tools supplied by a separate MCP process instead of imported.

#### Build

- `mcp_server.py`: FastMCP over stdio. Tools: `add_calendar_event`, `list_calendar_events`.
- `MultiServerMCPClient` per session, `env={"GOOGLE_TOKEN": token, "CALENDAR_TZ": tz}` at spawn, cached by session id.
- Agent entry point takes its tools from the MCP client. Zero direct imports of calendar tool functions.
- Tool schemas and descriptions are the product here — they travel over the wire and are all the model sees.

#### Cross-cutting

| Deliverable | This phase |
|---|---|
| Trace | JSONL also records the transport (`mcp:stdio`) and the spawned session id |
| Tests | tool schemas round-trip through the client; `build_agent` accepts MCP-loaded tools; I3 asserted over the wire |
| Docs | README: MCP section, how to run the inspector alone |
| Evals | +2 cases that exercise the MCP path |

#### Done when

- Same CLI commands as Phase 1 produce the same `Created …` result, and the event exists.
- `mcp dev mcp_server.py` lists both tools with full schemas; `docs/proof/mcp-inspector.txt` saved.
- `grep -n "from tools import add_calendar_event" pitu_agent.py` is empty.

#### Try it yourself

```
mcp dev mcp_server.py
GOOGLE_TOKEN=ya29... .venv/bin/python calendar_agent.py "list my next 3 events"
GOOGLE_TOKEN=ya29... .venv/bin/python calendar_agent.py "schedule standup tomorrow 9am for 15 min"
```
What to watch for: latency versus Phase 1 (subprocess spawn), and whether tool selection still holds with schemas arriving over MCP. Degradation here means a thin tool description, not a weak model.

---

### Phase 2.5 — Optional: Google's Calendar MCP server, read-only

**Objective:** prove the agent is a *multi-server* MCP client by adding Google's official Calendar MCP server alongside your own — yours writes, theirs reads. Timeboxed, droppable.

**Gate:** `gcloud services enable calendarmcp.googleapis.com` must succeed. It is a Developer Preview API; if it is not enabled for your project, record that in the README and skip the phase. Do not spend time working around it.

#### Build

- Second entry in the `MultiServerMCPClient` config pointing at `https://calendarmcp.googleapis.com/mcp/v1` over streamable-http, reusing the same browser access token as a header.
- **Filter the tool list.** Keep only `search_events`, `suggest_time`, `list_events`, `get_event`, `list_calendars`. Drop `create_event`, `update_event`, `delete_event`, `respond_to_event` — a write path you do not control violates I4/I5 and duplicates `add_calendar_event`.
- Trace records which server served each tool call (`mcp:google-calendar` vs `mcp:stdio`).

#### Done when

- `suggest_time` returns slots and `search_events` finds an existing event, both in the trace with the Google server named.
- The filtered tool list contains no write tools: a test asserts this against the registered names.
- Your `mcp_server.py` is still used for every write.

#### Try it yourself

```
.venv/bin/python calendar_agent.py "find a free hour next Tuesday afternoon, then book a review then"
```
What to watch for: the model mixing up which server owns which tool. If it tries `create_event` from the Google server, the filter is not applied.

#### If skipped

Nothing else in the spec changes. The README gets one line noting the API was unavailable, and the CV claim stays *MCP server author* rather than *multi-server client*.

---

### Phase 3 — Booking plus meeting-notes retrieval

**Objective:** the same booking, plus answers grounded in `notes/*.md` and cited.

#### Build

- `retrieval.py`: chunks `notes/*.md` by heading; builds an index of titles and first lines; `search_notes(question)`.
- Notes agent on `RESEARCH_MODEL` (defaults to `MODEL`), read-only, no calendar tools, no token (I10).
- `search_notes` becomes a third tool on the calendar agent, imported from `retrieval.py` and exposed through the same MCP server.
- Agent must cite `file: excerpt` in any answer drawn from a note.

#### Cross-cutting

| Deliverable | This phase |
|---|---|
| Trace | retrieval step recorded: query, files selected, whether a citation appeared |
| Tests | `test_retrieval.py`: chunking, index completeness, selection with a stub model, citation format, empty corpus, I10 |
| Docs | README: notes, citations, how to add a note |
| Evals | +3 cases: cited answer, uncited answer must be refused, no-notes-found |

#### Done when

- `GOOGLE_TOKEN=… .venv/bin/python calendar_agent.py "book the Q3 review for next Tuesday 3pm — use the launch decisions from our notes"` creates the event **and** the reply cites the note it drew on.
- A question the corpus cannot answer produces "no relevant notes", not an invented one.
- `docs/proof/rag-answer.md` holds a real transcript.

#### Try it yourself

```
.venv/bin/python -c "from retrieval import search_notes; print(search_notes('what did we decide about the Q3 launch'))"
.venv/bin/python calendar_agent.py "what did we decide about the Q3 launch?"
```
Ask three questions the corpus answers and one it does not. If selection is poor, change the index format, not the model.

---

### Phase 4 — HTTP service, still booking

**Objective:** the same capabilities over HTTP, tested with curl/Postman, with real per-user auth.

#### Build

- `server.py`: FastAPI; `GET /` (placeholder until P5), `POST /chat`, `POST /confirm`.
- Auth middleware: header → `tokeninfo` → `aud == GOOGLE_CLIENT_ID` → allowlist → rate limit. Fail closed. (I8)
- Timezone from `X-Timezone`, validated, falling back to `DEFAULT_TZ`. (I9)
- Redirect-free test setup: `ALLOWED_EMAILS` includes your account; a second account is used to prove the 403.
- Errors returned to the client are generic; detail goes to the trace only. `Authorization` redacted before logging.

#### Cross-cutting

| Deliverable | This phase |
|---|---|
| Trace | + request id, auth outcome, resolved timezone; one file per session |
| Tests | `test_server.py` (401 / 401 foreign aud / 403 / 429 / 200) and `test_tz.py` (valid, garbage, missing) |
| Docs | README: API section with copy-paste curl for every route |
| Evals | +3 auth cases: missing, foreign aud, non-allowlisted |

#### Done when

- `curl` with a real token and `X-Timezone: Europe/London` creates an event whose times match London, not the server zone.
- Missing header → 401 with a generic body; foreign `aud` → 401; non-allowlisted → 403; over the limit → 429.
- No response body contains a traceback or an echo of the token.
- The booking is visible in the calendar.

#### Try it yourself

```
.venv/bin/uvicorn server:app --reload
curl -i localhost:8000/chat -X POST -d '{"text":"hi"}' -H 'Content-Type: application/json'
curl -s localhost:8000/chat -X POST -H "Authorization: Bearer $TOKEN" -H "X-Timezone: Europe/London" \
     -H 'Content-Type: application/json' -d '{"text":"book lunch tomorrow at 1pm"}'
```
What to watch for: any time not matching the supplied zone. A 401 that leaks detail is an I2 failure.

---

### Phase 5 — React client: sign-in, voice, approval

**Objective:** the same booking, from a phone, in the user's own browser session.

#### Build

- `webapp/`: React + Vite + TypeScript. Components: `SignIn`, `MicButton`, `Transcript`, `Reply`, `Approval`. No router, no state library, no UI kit.
- `webapp/src/lib/auth.ts`: GIS token client; token in a module variable, never `localStorage` or a cookie.
- `webapp/src/lib/timezone.ts`: browser zone plus user override; `resolveTimezone()`.
- `SpeechRecognition` for input, `speechSynthesis` for the reply; text input always visible.
- React escapes by default — no `dangerouslySetInnerHTML`.
- One external script in `index.html`: GIS. Strict CSP.
- Approval flow: events with `attendees` or `create_meet` come back pending; `/confirm` requires the same `sub` (I6). Trace records pending, approved, cancelled.

#### Cross-cutting

| Deliverable | This phase |
|---|---|
| Trace | + pending / approved / cancelled, with the approving `sub` |
| Tests | Vitest for `resolveTimezone()`; a React test that a reply containing HTML renders as text |
| Docs | README: phone setup, tunnel, voice limitations, how to deploy nothing |
| Evals | live layer run once end to end; slug and cost recorded |

#### Done when

- From a phone over a tunnel: sign in, tap mic, speaking "book a haircut Friday at 11" creates the event at the phone's zone.
- Requesting an invite with an email shows Approve/Cancel first; Cancel leaves the calendar untouched.
- A reply containing `<script>` renders as text.
- `grep -c "cdn\.\|cdnjs\|jquery" webapp/index.html` is 0.

#### Try it yourself

```
npm --prefix webapp run dev
.venv/bin/uvicorn server:app --reload
cloudflared tunnel --url http://localhost:5173
```
What to watch for: misheard transcripts (cue for the Whisper path) and a confirmation time that disagrees with the phone's zone.

---

### Publish gate

Not a feature phase. The repo ships when every row is true.

| Check | Command or action |
|---|---|
| All invariants tested | `pytest -q` green, `test_invariants.py` present for I1–I10 |
| Contract evals green | `python evals/run_evals.py` |
| Live evals run and recorded | `python evals/run_evals.py --live`, cost in `report.md` |
| Proof artifacts exist | `docs/proof/`: inspector, rag answer, eval report, before/after, trace sample |
| No secrets tracked | `git ls-files \| grep -E "token\|credential\|\.env$"` empty |
| README reproduces from scratch | fresh clone, follow verbatim, time it |
| Limitations written | section 12 present in README |

---

## 8. Test plan

No test may touch Google, OpenRouter, or the network. Tests arrive with the phase that introduces the behaviour.

| File | Introduced | Tests |
|---|---|---|
| `tests/test_tools.py` | P1 | `parse_date_only` accepts messy and rejects bad; `coerce_bool` truth table; `build_rrule` table (none, daily, weekly BYDAY, interval, count vs until, UNTIL format); case-insensitive dedupe; failure returns `Failed`, never raises; token absent from schema (I3) |
| `tests/test_agent.py` | P1 | `build_agent` accepts injected tools; write budget blocks the second call (I4); failure text never starts with `Created` (I5) |
| `tests/test_mcp.py` | P2 | tool schemas survive the client; agent built from MCP tools calls the same name and args |
| `tests/test_retrieval.py` | P3 | chunking on headings; index includes every note; selection with a stub model; citation format; empty corpus; notes agent has no calendar tools (I10) |
| `tests/test_tz.py` | P4 | valid zone used; garbage falls back; missing header falls back; `UNTIL` computed in the supplied zone (I9) |
| `tests/test_server.py` | P4 | 401 missing, 401 foreign `aud`, 403 not allowlisted, 429 over limit, 200 success, no traceback in body (I8) |
| `tests/test_invariants.py` | P1, grown each phase | I1 no token in outbound payload; I2 no token in trace; I6 confirm with foreign `sub` rejected |
| `webapp/src/lib/timezone.test.ts` | P5 | override wins; browser zone used; empty falls back |

Mechanism: `monkeypatch` the service factory; a fake chat model for the agent; `TestClient` for routes; Vitest for the frontend helper. No production signatures bent for testability.

## 9. Eval plan

Starts in Phase 1 and grows with the slices.

1. **Contract evals (default, deterministic).** `evals/cases.jsonl`, one row per model-shaped argument set (`id`, `args`, `expect`). `python evals/run_evals.py` writes `evals/report.md`. Rows are added by the phase that makes them meaningful: messy dates and booleans in P1, the MCP path in P2, citations in P3, auth in P4.
2. **Live agent evals (opt-in).** `python evals/run_evals.py --live` runs the loop against `MODEL` and `RESEARCH_MODEL`, recording both slugs, pass rate, and token cost. First run at Phase 5, re-run at the publish gate. Never part of `pytest`.

## 10. Metrics — before and after

Baseline measured in Phase 0 (`docs/proof/before-after.md`). Do not backfill. Re-measure at Phase 2, Phase 4, and the publish gate.

| Metric | How measured |
|---|---|
| Import/runtime bugs | count, by reproduction |
| Dead files | `agents.py`, `add_event.py` |
| Tests collected | `pytest --collect-only -q \| tail -1` |
| Contract eval pass rate | `evals/report.md` |
| Tools exposed over MCP | inspector |
| Timezone definitions in source | `grep -rn "Asia/Singapore"` |
| Secret files in repo | `git ls-files \| grep -E "token\|credential"` |
| Invariants covered by test | section 3, count of 10 |
| End-to-end booking works via | CLI (P1), MCP (P2), + notes (P3), HTTP (P4), phone (P5) |

If a number is bad — a low live pass rate, a weak model — publish it in Limitations rather than tuning it away.

## 11. Documentation requirements

The README grows one section per phase; the final document has these in order:

1. What it is, one paragraph, no adjectives.
2. The architecture diagram from `docs/diagrams.md`.
3. Quickstart: Google Cloud OAuth client setup (authorized JS origin), `cp .env.example .env` with the section 5 variables, `npm --prefix webapp ci && npm --prefix webapp run build`, then `uvicorn server:app`.
4. Phone access: `cloudflared tunnel --url http://localhost:8000`, with the "laptop must be awake, tunnel URL changes each run" caveats.
5. CLI and MCP: how to book without the UI, and how to run the server alone in the inspector.
6. Tests and evals with pasted real output.
7. Limitations, honest and specific.

`docs/proof/` must hold: `mcp-inspector.txt`, `rag-answer.md`, `eval-report.md`, `before-after.md`, `trace-sample.jsonl`.

## 12. Limitations to disclose

Belong in the README because a reviewer would otherwise discover them.

- Tokens expire in about an hour; there is no refresh, so the user re-authenticates.
- The Google OAuth app runs in Testing mode: 100 user cap, unverified-app warning.
- Conversation text goes to a third-party model provider; `MODEL` is swappable for another slug.
- The `notes/` corpus is synthetic and shared across users.
- One laptop, one process, in-memory sessions; a restart logs everyone out.
- The tunnel URL rotates per run.

## 13. Open questions

| # | Question | Default if unanswered |
|---|---|---|
| Q1 | Web Speech API only, or add a Whisper upload path? | Web Speech only |
| Q2 | Notes agent on a cheaper model than the calendar agent? | `RESEARCH_MODEL` defaults to `MODEL` |

## 14. Change log

- Draft 1 — created from the design discussion: OpenRouter-configurable model, client-held Google tokens, per-session MCP subprocess, RAG over a bundled corpus, HITL approval, eval harness.
- Draft 2 — frontend is React + Vite + TypeScript rather than a plain page; timezone is per-request from the client with a validated fallback; scope section removed so nothing is stated in the negative.
- Draft 3 — retrieval is a second OpenRouter agent over a notes index, not an embedding index; the local embedding model and Ollama dependency are removed; `RESEARCH_MODEL` added; I10 added.
- Draft 4 — every phase ends with a manual **Try it yourself** step run against OpenRouter between phases; Phase 1 is the first one that needs a key and now installs `langchain-openai`.
- Draft 5 — phases are vertical slices: each from Phase 1 ends with a real event created through that phase's interface. Audit, tests, docs, and evals are per-phase deliverables instead of late phases; a publish gate replaces Phases 6–9.
- Draft 6 — OAuth starts in Phase 1: `login.py` (Desktop client, `InstalledAppFlow`) is the token source for P1–P3; Phase 4 switches to the browser flow with a Web client. Entry point from Phase 1 is a single script run directly.
- Draft 7 — Phase 2.5 added as an optional, gated, read-only integration with Google's official Calendar MCP server, proving multi-server MCP. Writes stay on the project's own server.
