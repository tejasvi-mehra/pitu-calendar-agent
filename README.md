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

## Limitations

- Access tokens expire in about an hour. The client caches the token in
  `sessionStorage` for that hour; after it lapses a Google popup reappears.
- The OAuth app runs in **Testing** mode: 100 user cap and an "unverified app" warning
  on the consent screen.
- Conversation text goes to a third-party model provider. `MODEL` is swappable.
- The `notes/` corpus is synthetic and shared across users.
- One laptop, one process, in-memory sessions. A restart logs everyone out.
- `sessionStorage` is readable by injected script. Bounded by the one-hour expiry and
  the server re-verifying every token, but it is the reason this is not a public
  deployment.
- Deleting is capped at one event per request by the tool-call middleware, but there is
  no confirmation dialog; the model is instructed to delete only what the user named.

## Licence

Source-available for portfolio review.
