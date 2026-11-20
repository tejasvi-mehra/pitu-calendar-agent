# CLAUDE.md — Pitu - Calendar Agent

You are working on a voice-and-text Google Calendar agent. Read this file before
touching code. It is the map; `SPEC.md` is the contract; `webapp/SPEC.md` is the client
design.

---

## 1. What this is

A user signs in with **their own** Google account in the browser, says or types a
request, and the agent books, moves, cancels or answers questions about events on that
calendar. Chat history lives in the tab; the server stores no Google credentials.

The two claims that matter, and the ones a reviewer will test:

1. **The Google access token never reaches the model provider.** It goes browser →
   server → MCP child process only.
2. **The server stores no refresh token.** Nothing credential-shaped exists on disk.

Breaking either is a release blocker, not a nit.

---

## 2. Architecture

```
webapp (React + Vite + TS)
  └─ GIS token in sessionStorage (1h, tab-scoped)
        │ POST /chat   Authorization: Bearer …   X-Timezone: Asia/Hong_Kong
        ▼
server.py (FastAPI)
  ├─ security_headers     CSP, nosniff, DENY framing
  ├─ verify()             Bearer → tokeninfo → aud → allowlist → rate limit
  ├─ resolve_tz()         IANA-validated, falls back to DEFAULT_TZ
  └─ pitu_agent.run(text, tz, token)
        │
        ├─ trace()  → traces/<session>.jsonl  (tokens redacted)
        ├─ build_agent(tools)  ← tools loaded over MCP
        │
        ├─ MCP stdio child:  mcp_server.py
        │     GOOGLE_TOKEN / CALENDAR_TZ passed in env
        │     tools.py → Google Calendar API
        │
        └─ retrieval.py (search_notes)
              └─ notes agent on RESEARCH_MODEL, read-only, no token
```

**Model calls go to OpenRouter** (`langchain_openai.ChatOpenAI` with a custom
`base_url`). There is no local model. `MODEL` is any tool-calling slug.

---

## 3. Repository layout

| Path | Role |
|---|---|
| `server.py` | FastAPI app: auth, timezone, `/chat`, `/me`, static assets, CSP |
| `pitu_agent.py` | `build_model()`, `build_agent()`, `mcp_client()`, `run()`, CLI `main()` |
| `mcp_server.py` | FastMCP server over stdio; exposes 5 tools |
| `tools.py` | The only file that talks to Google. `make_calendar_tools(token, tz)` |
| `retrieval.py` | Notes index, notes agent, citation parser |
| `prompt.py` | The system prompt. Behaviour lives here more than in code |
| `trace.py` | Append-only JSONL audit log with token redaction |
| `login.py` | CLI-only OAuth (Desktop client). Never imported by the server |
| `notes/*.md` | Synthetic meeting notes the retrieval agent searches |
| `webapp/` | React client; `src/lib/*` is framework-free logic |
| `tests/` | pytest, no network. `test_invariants.py` maps 1:1 to SPEC §3 |
| `evals/` | Contract layer (free) and live layer (costs money) |
| `docs/proof/` | Artifacts a reviewer opens |
| `traces/` | Gitignored runtime output |

---

## 4. Build and run

```bash
python -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env                 # fill the five required values
echo "VITE_GOOGLE_CLIENT_ID=<web client id>" > webapp/.env
npm --prefix webapp ci && npm --prefix webapp run build

.venv/bin/uvicorn server:app --port 8000       # UI + API
npm --prefix webapp run dev                    # :5173, proxies to :8000
```

Required environment:

| Var | Used by |
|---|---|
| `OPENROUTER_API_KEY`, `MODEL` | `build_model()` |
| `GOOGLE_CLIENT_ID` | `server.verify()` audience check — must be the **Web** client |
| `ALLOWED_EMAILS` | `server.verify()`; empty means **everyone denied** |
| `GOOGLE_CREDENTIALS_PATH` | `login.py` only (Desktop client JSON, outside the repo) |
| `VITE_GOOGLE_CLIENT_ID` | the React client; same value as `GOOGLE_CLIENT_ID` |

Checks, in the order to run them:

```bash
.venv/bin/python -m pytest -q          # 89 tests, no network, no key
npm --prefix webapp test               # 9 tests
.venv/bin/python -m ruff check .       # clean
.venv/bin/python evals/run_evals.py    # contract: 10/10
.venv/bin/python evals/run_evals.py --live   # costs cents
```

---

## 5. How it actually flows

### A request

1. `POST /chat {text}` with `Authorization` and `X-Timezone`.
2. `verify()` calls Google `tokeninfo`. Checks `aud == GOOGLE_CLIENT_ID`, email in the
   allowlist, `calendar.events` in scope, then the per-account rate limit. Any failure
   is 401/403/429 with a generic body.
3. `resolve_tz()` validates the header against the IANA database.
4. `pitu_agent.run()` prepends `Today is …` and opens a fresh MCP session:
   `MultiServerMCPClient` spawns `mcp_server.py` with the token in its environment.
5. Tools load over MCP. `build_agent` wires them plus two `ToolCallLimitMiddleware`
   guards (create 1, delete 1).
6. `astream` runs the loop; every node is written to `traces/<session>.jsonl`.
7. The final assistant message is returned as `{"session", "tz", "reply"}`.

### Why MCP

The agent never imports a calendar function. `test_mcp.py` asserts the tool list
arrives over the wire, and `test_invariants.py::test_I3` asserts no schema contains a
token. If you add a tool, add it to `mcp_server.py`, not to the agent's imports.

### Why the token is in the child's env

`make_calendar_tools(token, tz)` binds the credential at construction. The tool's
signature has no token field, so the model cannot emit one and nothing credential-shaped
ever enters a message. Do not "simplify" this by passing the token as an argument.

---

## 6. Design system (client)

`webapp/specs/` is the source of truth. `00-foundation.md` holds tokens and the
prohibitions; `01-shell.md`, `02-composer.md`, `03-history.md` cover each surface.

Non-negotiables:

- Warm paper + terracotta. No indigo, violet, or blue accent; no gradients on controls.
- All colour and font through `:root` tokens. No literals outside the token block.
- `:focus-visible` on every control, 2px accent.
- One looping animation only: the mic pulse. Everything else is state-triggered.
- Every user-facing string lives in `lib/copy.ts`.
- React escapes by default. Never `dangerouslySetInnerHTML`.

Run `node ~/.claude/skills/hallmark/scripts/sloplint.mjs webapp/src --genre modern-minimal`
before proposing UI changes; it must report zero findings.

---

## 7. State and storage

| Where | What | Lifetime |
|---|---|---|
| Module var in `lib/auth.ts` | access token | until reload |
| `sessionStorage` | token + expiry (`pitu.token`, `pitu.expires`) | until tab closes |
| `localStorage` | `pitu.autologin`, `pitu.email`, `pitu.voice` | until sign-out |
| Server memory | rate-limit deques, sessions | until restart |

Never put the token in `localStorage`, a cookie, or a log line.

---

## 8. Invariants

`SPEC.md` §3 lists ten. `tests/test_invariants.py` covers I1–I7 directly and asserts
I8–I10 exist in `test_server.py` / `test_retrieval.py`. If you change behaviour, run
that file first — it is the fastest way to find out what you broke.

The three most fragile:

- **I1/I2**: adding any logging, tracing, or error detail that includes the
  `Authorization` header or a `ya29.` string breaks them. Grep before committing.
- **I3**: adding a `token` parameter to any tool breaks it.
- **I4**: removing or raising a `ToolCallLimitMiddleware` limit breaks it.

---

## 9. Gotchas that cost time

- **OpenRouter's base URL must end in `/v1`.** A missing segment gives a 404 that looks
  like a model problem. `build_model()` normalises it; don't remove that.
- **An empty `OPENROUTER_API_KEY` silently falls back to `OPENAI_API_KEY`** in the
  OpenAI SDK, producing a confusing 401. `build_model()` rejects both cases early.
- **`prompt: ""` in GIS still opens a popup.** Google has no silent auth for token
  clients. The token cache in `sessionStorage` is what makes refresh work — not
  `prompt`.
- **Recursion limit.** Each tool call costs ~3 graph steps. Two-tool prompts exceed the
  old limit of 8 and surface as `ExceptionGroup: unhandled errors in a TaskGroup`, not
  as a recursion error. `RECURSION_LIMIT` defaults to 25.
- **`recursion_limit` errors arrive as ExceptionGroups.** When debugging an
  `ExceptionGroup`, unwrap it: the cause is usually a LangGraph error inside.
- **The date must be injected in `run()`, not `main()`.** The server path skips
  `main()`; injecting only there made the model ask for today's date.
- **MCP tools are async-only.** `agent.stream()` fails with
  `NotImplementedError: StructuredTool does not support sync invocation`. Use
  `astream()`.
- **`MultiServerMCPClient` takes `env` at construction**, not per call. One client per
  session.
- **`FastMCP.add_tool` needs a plain function.** Pass `t.func` with `name=` and
  `description=`, not a LangChain `StructuredTool`.
- **`require_token()` raises when no token is set**, rather than sending an
  unauthenticated request.

---

## 10. Testing

- pytest never touches the network. Google is replaced by `monkeypatch` on
  `tools.get_calendar_service`; the model is replaced by a stub or not called at all.
- Use `Fixture` in `evals/run_evals.py` as the pattern for a fake Google service.
- Put a new invariant test in `test_invariants.py`, not a new file.
- Tests set env vars **unconditionally**, not with `setdefault` — an earlier module
  may have run `load_dotenv()` and left an empty string.

---

## 11. Known gaps

Listed in `README.md` under "Known gaps". The two worth knowing while editing:

1. **Delete has no server-side confirmation.** The prompt requires the model to ask and
   wait for a yes, and the middleware caps it at one call per request, but nothing
   enforces a two-step flow. A `/confirm` round trip is the fix.
2. **No CI.** Run the five commands in §4 before you push.

---

## 12. Changing things safely

| Change | Also update |
|---|---|
| New tool | `mcp_server.py`, `prompt.py`, `tests/test_mcp.py`, `test_invariants.py::I3` |
| Prompt rules | Re-run `evals/run_evals.py --live`; contract evals will not catch it |
| New env var | `.env.example`, README quickstart, §4 of this file |
| Client component | `webapp/specs/`, `lib/copy.ts`, sloplint |
| Auth logic | `tests/test_server.py`, `tests/test_security.py` |
| Anything touching the token | `tests/test_invariants.py` first |

This repository has no CV files; anything named `CV_MASTER.md` or `render/cv.css` belongs
to a different project and is out of scope here.
