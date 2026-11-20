# Pitu - Calendar Agent

A voice-and-text Google Calendar agent. You sign in with your own Google account, say
or type what you want, and Pitu books, moves, cancels or answers questions about events
on the calendar you already use. The server holds no Google credentials, and the model
provider never sees an access token.

![Architecture](docs/diagrams.md)

## How it works

```
webapp (React + Vite)  --Bearer token + X-Timezone-->  FastAPI
                                                          |
                              auth: header -> tokeninfo -> aud -> allowlist -> rate limit
                              timezone: IANA-validated, falls back to DEFAULT_TZ
                                                          |
                              agent (messages only) ---> OpenRouter   [MODEL]
                              notes agent (read-only) --> OpenRouter   [RESEARCH_MODEL]
                                                          |
                              tool dispatch (token from request context)
                                                          |
                              mcp_server subprocess (token in env)
                                                          |
                              Google Calendar API
```

Five MCP tools: `add_calendar_event`, `list_calendar_events`, `update_calendar_event`,
`delete_calendar_event`, `search_notes`.

## Quickstart

### 1. Google Cloud

1. Create a project, enable the **Google Calendar API**.
2. **OAuth consent screen** → External → add yourself under **Test users**.
3. Create two OAuth clients, both with **Use this client for an AI-powered agent** ticked:
   - **Desktop app** `pitu-calendar-agent-cli` — used by `login.py` for the CLI.
   - **Web application** `pitu-web` — add `http://localhost:8000` as an Authorized
     JavaScript origin. No redirect URI needed.
4. Save the Desktop client JSON outside the repo.

### 2. Configure

```bash
cp .env.example .env          # fill OPENROUTER_API_KEY, MODEL, GOOGLE_CLIENT_ID,
                              # GOOGLE_CREDENTIALS_PATH, ALLOWED_EMAILS
echo "VITE_GOOGLE_CLIENT_ID=<web client id>" > webapp/.env
```

`GOOGLE_CLIENT_ID` and `VITE_GOOGLE_CLIENT_ID` must be the **Web** client. The Desktop
client is for `login.py` only; the server rejects its tokens by audience.

### 3. Run

```bash
.venv/bin/pip install -r requirements.txt
npm --prefix webapp ci && npm --prefix webapp run build
.venv/bin/uvicorn server:app --port 8000
```

Open <http://localhost:8000>, sign in, and ask for a meeting.

### 4. Phone

```bash
cloudflared tunnel --url http://localhost:8000
```

The laptop must stay awake and the tunnel URL changes each run. Add the tunnel origin
to the OAuth client's authorized origins if you want sign-in to work there.

## CLI and MCP

```bash
export GOOGLE_TOKEN=$(.venv/bin/python login.py --print-token)
.venv/bin/python pitu_agent.py "book a 30 min meeting tomorrow at 4pm"

mcp dev mcp_server.py     # inspect the server alone
```

## Tests and evals

```
76 passed in 1.32s                      # pytest, no network, no API key
9 passed                                # vitest, webapp/src/lib
contract: 10/10 passed                  # evals/run_evals.py
live: 4/4 passed                        # evals/run_evals.py --live
```

The contract layer feeds model-shaped arguments into the tool with a fake Google
service. The live layer runs the real agent against the configured model and costs
cents. Both write `evals/report.md`.

Proof artifacts are in `docs/proof/`: `mcp-inspector.txt`, `rag-answer.md`,
`eval-report.md`, `before-after.md`, `trace-sample.jsonl`.

## Known gaps in this repository

Not limitations of the design — work an operator should do before public use.

- **The server has never been load-tested.** One process, in-memory rate-limit state and
  in-memory sessions. A restart drops every session and resets rate limits.
- **`/chat` has no timeout.** A slow model holds the request open; a reverse proxy
  timeout is the only bound today.
- **No CSRF token.** The API is bearer-only and never sets a cookie, so classic CSRF
  does not apply, but do not add cookie auth without adding CSRF protection.
- **`sessionStorage` holds the access token.** Readable by injected script. See
  Security below.
- **The `notes/` corpus ships with the repo** and is shared by every user.
- **No CI.** Tests and lints run locally only.
- **Delete has no server-side confirmation.** The prompt requires the model to confirm
  first, and the middleware caps deletion at one call per request, but nothing on the
  server enforces it. A two-step `/confirm` endpoint is the fix.

## Security notes

| Item | Current state | Operator should |
|---|---|---|
| Token at rest | `sessionStorage`, 1-hour expiry enforced client-side | Add a CSP so injected script cannot read it; see below |
| Allowlist | Empty `ALLOWED_EMAILS` rejects everyone (fail closed) | Set it explicitly |
| Rate limit | Per-account, in-memory, 10/min default | Put a real limiter at the proxy for multi-instance |
| Token verification | `tokeninfo` on every request, audience checked | Nothing; keep it |
| Logging | `Authorization` redacted before any write | Audit `traces/` retention |
| Third-party scripts | Google Identity Services only | Keep it that way; see `test_invariants.py` |

A Content-Security-Policy that allows only what the app needs:

```python
@app.middleware("http")
async def csp(request, call_next):
    response = await call_next(request)
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' https://accounts.google.com; "
        "connect-src 'self' https://accounts.google.com https://oauth2.googleapis.com; "
        "frame-src https://accounts.google.com; "
        "img-src 'self' data:; style-src 'self' 'unsafe-inline'"
    )
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response
```

## Production checklist

| Area | Todo |
|---|---|
| Google | Publish the OAuth app (remove Testing mode); restrict the Web client to your domain |
| Hosting | HTTPS only, so `sessionStorage` sits behind a secure origin |
| Process | More than one worker needs shared rate-limit state (Redis) and sticky sessions |
| Models | Pin a paid slug; free-tier limits are 50 requests/day |
| Observability | Ship `traces/` somewhere durable with a retention rule |
| Data | Decide how long transcripts are kept; they carry meeting titles and names |
| CI | `pytest`, `npm test`, `ruff`, `npm run build` on every push |
| Abuse | A global per-IP limit in front of the per-account one |

## Licence

Source-available for portfolio review.
