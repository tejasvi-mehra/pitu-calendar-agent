# Pitu - Calendar Agent — system and flow diagrams

Preview: `Cmd+Shift+V`. Diagrams use only baseline Mermaid syntax: no `actor` keyword, no `alt` blocks, no quotes, no slashes. If a sequence diagram still fails, your preview extension's Mermaid is old — update it, or paste the block into mermaid.live.

---

## 1. System design — three trust zones

```mermaid
flowchart TD
    subgraph DEVICE["Zone 1 — user's phone or laptop (untrusted by server)"]
        UI["index.html<br/>mic, transcript, reply"]
        GIS["Google Identity Services<br/>only third-party script"]
        TOK["access token ya29…<br/>JS variable, ~1h, no refresh"]
        UI -->|"initTokenClient"| GIS
        GIS -->|"grants"| TOK
    end

    subgraph HOST["Zone 2 — your server (you trust it, it trusts almost nothing)"]
        S["FastAPI<br/>/ and /chat and /confirm"]
        MW["auth middleware<br/>aud, allowlist, rate limit<br/>Authorization redacted before logging"]
        CTX["request contextvar<br/>token held here only"]
        AG["Agent — LangChain<br/>system prompt + messages"]
        MCP["mcp_server subprocess<br/>spawned per session, token in env"]
        RAG["notes agent, read-only<br/>reads notes corpus, shared"]
        TR["traces/*.jsonl<br/>token redacted"]
        S --> MW --> CTX
        MW --> AG
        AG -->|"tool dispatch, token from contextvar"| MCP
        AG --> RAG
        AG --> TR
    end

    subgraph EXT["Zone 3 — third parties"]
        OR["OpenRouter<br/>model provider"]
        GC["Google Calendar API<br/>validates every call"]
    end

    TOK -->|"HTTPS Bearer, per request"| S
    AG -->|"messages only — NO token"| OR
    MCP -->|"Bearer, server-side only"| GC

    style TOK fill:#fee,stroke:#c00
    style CTX fill:#fee,stroke:#c00
```

The one-line rule this encodes: **the red boxes never touch the OpenRouter arrow.**

---

## 2. Use cases

### UC-1 · Sign in and bind a session

```mermaid
sequenceDiagram
    participant U as User
    participant B as Web Browser
    participant G as Google Identity
    participant S as API Server

    U->>B: open the app
    B->>G: request access token for calendar events
    G-->>B: access token, valid 1 hour
    B->>S: GET with Bearer token header
    S->>G: GET tokeninfo
    G-->>S: aud, email, scope, exp
    S->>S: check aud and email allowlist
    S-->>B: page ready, session bound to sub
    B-->>U: signed in, ready to schedule
```

### UC-2 · Book a simple event (happy path)

```mermaid
sequenceDiagram
    participant U as User
    participant B as Web Browser
    participant S as API Server
    participant O as OpenRouter
    participant M as MCP Server
    participant C as Google Calendar

    U->>B: book lunch with Priya Thursday 1pm by voice
    B->>B: Web Speech to text, transcript editable
    B->>S: POST chat with Bearer token and text
    S->>S: auth ok, token bound to request context
    S->>O: messages only, no token
    O-->>S: tool_call add_calendar_event
    S->>S: middleware allows 1 write call only
    S->>M: spawn once per session, token in env
    M->>C: events insert with Bearer
    C-->>M: event id and Meet link
    M-->>S: Created Lunch with Priya
    S->>O: second completion with tool result
    O-->>S: reply text
    S-->>B: reply text, trace written token redacted
    B-->>U: shown and spoken aloud
```

### UC-3 · Book an event that needs approval (HITL)

```mermaid
sequenceDiagram
    participant U as User
    participant B as Web Browser
    participant S as API Server
    participant M as MCP Server
    participant C as Google Calendar

    Note over S: model returned a tool_call with attendees or Meet
    S->>S: store pending action with user sub
    S-->>B: 202 pending, resolved event shown
    B-->>U: Approve or Cancel
    U->>B: tap Approve
    B->>S: POST confirm with token resubmitted
    S->>S: tokeninfo sub must equal pending sub
    S->>M: spawn with token in env
    M->>C: events insert with Bearer
    C-->>M: event id
    M-->>S: Created
    S-->>B: 200 confirmed
    B-->>U: booked and invited
```

### UC-4 · Rejected at the gate

```mermaid
sequenceDiagram
    participant U as User
    participant B as Web Browser
    participant G as Google Identity
    participant S as API Server

    U->>B: send a request
    B->>S: POST chat
    S->>S: no header, or foreign aud, or email not allowed, or rate limited
    S-->>B: 401 or 403 or 429, generic message only
    B-->>U: sign in again, or not permitted, or too many requests
    Note over B,S: nothing reaches the model, nothing is booked
    U->>B: sign in again
    B->>G: request access token
    G-->>B: fresh token
```

### UC-5 · Booking fails at Google

```mermaid
sequenceDiagram
    participant U as User
    participant B as Web Browser
    participant S as API Server
    participant M as MCP Server
    participant C as Google Calendar

    S->>M: dispatch with token in env
    M->>C: events insert with Bearer
    C-->>M: 401 expired or 403 quota or 5xx
    M-->>S: Failed with reason
    S-->>B: nothing booked, reason, no stack trace
    B-->>U: if token expired, sign in and retry manually
    B-->>U: if quota or outage, try again later
    Note over S: write call budget spent, no automatic retry
```

---

## 3. Failure cases — full branch map

```mermaid
flowchart TD
    REQ["POST /chat"] --> H{"Authorization<br/>header present?"}
    H -->|"no"| E401["401 Sign in with Google again"]
    H -->|"yes"| T{"tokeninfo ok<br/>and aud equals CLIENT_ID?"}
    T -->|"no"| E401B["401 That token is not for this app"]
    T -->|"yes"| AL{"email in<br/>ALLOWED_EMAILS?"}
    AL -->|"no"| E403["403 You are not permitted to use this service"]
    AL -->|"yes"| RL{"rate limit<br/>remaining?"}
    RL -->|"no"| E429["429 Too many requests, wait a minute"]
    RL -->|"yes"| MOD{"OpenRouter<br/>reachable?"}

    MOD -->|"429 or timeout"| E502["502 Model unavailable, nothing was booked"]
    MOD -->|"ok"| TOOL{"model chose a<br/>valid tool call?"}
    TOOL -->|"no tool call"| EPLAIN["200 plain answer, no booking"]
    TOOL -->|"bad args"| EVAL["200 tool returns Failed reason<br/>model tells user, NO retry"]
    TOOL -->|"valid, needs approval"| PEND["pending action stored with sub<br/>Approve or Cancel shown"]
    TOOL -->|"valid, simple"| CAL

    PEND --> PC{"confirm token<br/>sub matches pending sub?"}
    PC -->|"no"| E403B["403 Wrong account for this action"]
    PC -->|"yes"| CAL{"Google call<br/>result?"}

    CAL -->|"401 expired"| E401C["401 Token expired mid-session<br/>client re-runs sign-in, request is not retried blindly"]
    CAL -->|"403 quota"| EQ["200 Nothing booked, daily quota exceeded"]
    CAL -->|"5xx"| E5["502 Nothing booked, Calendar unavailable"]
    CAL -->|"ok"| OK["Created, trace written, token redacted"]

    style E401 fill:#fee
    style E401B fill:#fee
    style E403B fill:#fee
    style PEND fill:#ffe,stroke:#c90
    style OK fill:#efe
```
