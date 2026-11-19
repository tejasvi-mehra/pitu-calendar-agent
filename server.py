"""Pitu HTTP service: browser-held Google tokens, no server-side credential store.

Every route fails closed. The access token arrives per request, is validated against
Google's tokeninfo endpoint, and is handed to a per-session MCP subprocess. It is
never logged, never traced, and never sent to the model provider (I1, I2, I8).
"""

import asyncio
import os
import uuid
from collections import defaultdict, deque
from datetime import datetime
from pathlib import Path
from typing import Annotated

import httpx
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

load_dotenv()

import pitu_agent  # noqa: E402
from trace import trace  # noqa: E402

app = FastAPI(title="Pitu - Calendar Agent")

TOKENINFO = "https://oauth2.googleapis.com/tokeninfo"
_rl: dict[str, deque] = defaultdict(deque)


class ChatRequest(BaseModel):
    text: str


class TokenInfo(BaseModel):
    aud: str = ""
    email: str = ""
    scope: str = ""
    expires_in: str = "0"


def _allowed() -> set[str]:
    return {e.strip().lower() for e in os.environ.get("ALLOWED_EMAILS", "").split(",") if e.strip()}


def _check_rate(sub: str) -> None:
    limit = int(os.environ.get("RATE_LIMIT_PER_MIN", "10"))
    now = datetime.now().timestamp()
    q = _rl[sub]
    while q and now - q[0] > 60:
        q.popleft()
    if len(q) >= limit:
        raise HTTPException(429, "Too many requests, wait a minute")
    q.append(now)


async def verify(
    authorization: Annotated[str | None, Header()] = None,
) -> dict:
    """Header present -> tokeninfo -> aud -> allowlist -> rate limit. Fail closed."""
    if not authorization or not authorization.startswith("Bearer "):
        trace("auth", "verify", kind="auth_reject", reason="missing_header")
        raise HTTPException(401, "Sign in with Google again")
    token = authorization.removeprefix("Bearer ").strip()

    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.get(TOKENINFO, params={"access_token": token})
    except httpx.HTTPError:
        trace("auth", "verify", kind="auth_reject", reason="tokeninfo_unreachable")
        raise HTTPException(401, "Sign in with Google again")
    if r.status_code != 200:
        trace("auth", "verify", kind="auth_reject", reason="tokeninfo_rejected")
        raise HTTPException(401, "Sign in with Google again")

    info = TokenInfo(**{k: v for k, v in r.json().items() if k in TokenInfo.model_fields})
    if not info.aud or info.aud != os.environ.get("GOOGLE_CLIENT_ID", ""):
        trace("auth", "verify", kind="auth_reject", reason="wrong_audience")
        raise HTTPException(401, "That token is not for this app")
    allowed = _allowed()
    if allowed and info.email.lower() not in allowed:
        trace("auth", "verify", kind="auth_reject", reason="not_allowlisted")
        raise HTTPException(403, "You are not permitted to use this service")
    # a token granted before the calendar scope existed would 403 deep inside Google;
    # fail here with something the user can act on
    if "calendar.events" not in info.scope:
        trace("auth", "verify", kind="auth_reject", reason="missing_scope")
        raise HTTPException(
            403,
            "This sign-in did not grant calendar access. Sign out and sign in again.",
        )

    _check_rate(info.email.lower())
    trace("auth", "verify", kind="auth_ok", email=info.email)
    return {"token": token, "email": info.email, "sub": info.email.lower(), "scope": info.scope}


def resolve_tz(x_timezone: str | None) -> str:
    """IANA-validated; anything unknown falls back and never raises (I9)."""
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

    default = os.environ.get("DEFAULT_TZ", "Asia/Singapore")
    if not x_timezone:
        return default
    try:
        ZoneInfo(x_timezone)
        return x_timezone
    except (ZoneInfoNotFoundError, ValueError):
        return default


DIST = Path(__file__).resolve().parent / "webapp" / "dist"


@app.get("/")
def index():
    page = DIST / "index.html"
    if page.exists():
        return FileResponse(page)
    return JSONResponse({"service": "Pitu - Calendar Agent", "ui": "not built yet"})


@app.get("/assets/{path:path}")
def assets(path: str):
    f = (DIST / "assets" / path).resolve()
    if f.is_file() and DIST in f.parents:
        return FileResponse(f)
    raise HTTPException(404, "Not found")


# Vite copies public/ to the dist root; serve those files too (favicon, logo).
@app.get("/{name}.{ext}")
def public_file(name: str, ext: str):
    if ext not in {"png", "svg", "ico", "webmanifest", "txt", "json"}:
        raise HTTPException(404, "Not found")
    f = (DIST / f"{name}.{ext}").resolve()
    if f.is_file() and DIST in f.parents:
        return FileResponse(f)
    raise HTTPException(404, "Not found")


@app.get("/me")
async def me(who: Annotated[dict, Depends(verify)]):
    return {"email": who["email"], "scope": who["scope"]}


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/chat")
async def chat(
    body: ChatRequest,
    who: Annotated[dict, Depends(verify)],
    x_timezone: Annotated[str | None, Header()] = None,
):
    tz = resolve_tz(x_timezone)
    session = uuid.uuid4().hex[:8]
    trace(session, "chat", kind="request", tz=tz, email=who["email"], text=body.text[:200])
    try:
        reply = await pitu_agent.run(body.text, session=session, tz=tz, token=who["token"])
    except Exception as e:
        # generic to the caller; detail stays in the trace
        trace(session, "chat", kind="error", error=f"{type(e).__name__}")
        raise HTTPException(502, "The agent could not complete that request")
    return {"session": session, "tz": tz, "reply": reply}


@app.exception_handler(Exception)
async def unhandled(request, exc):  # no stack traces to clients
    trace("http", "unhandled", kind="error", path=str(request.url.path))
    return JSONResponse({"detail": "Internal error"}, status_code=500)
