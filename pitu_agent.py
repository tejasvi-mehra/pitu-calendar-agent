import json
import os
import sys
import uuid
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

load_dotenv()

from langchain.agents import create_agent  # noqa: E402
from langchain.agents.middleware import ToolCallLimitMiddleware  # noqa: E402
from langchain_openai import ChatOpenAI  # noqa: E402

from prompt import SYSTEM_PROMPT  # noqa: E402
from tools import DEFAULT_TZ, make_calendar_tools, require_token  # noqa: E402
from trace import trace  # noqa: E402


def build_model() -> ChatOpenAI:
    """The only place a chat model is constructed. P2-P5 call this."""
    key = (os.environ.get("OPENROUTER_API_KEY") or "").strip()
    model = (os.environ.get("MODEL") or "").strip()
    # OpenAI SDKs silently fall back to OPENAI_API_KEY when this is empty, which
    # produces a 401 that looks like a bad key. Fail here with a clear message.
    if not key:
        raise RuntimeError("OPENROUTER_API_KEY is empty")
    if not key.startswith("sk-or-"):
        raise RuntimeError("OPENROUTER_API_KEY must be an OpenRouter key (sk-or-...)")
    if not model:
        raise RuntimeError("MODEL is empty; set an OpenRouter slug that supports tools")
    # OpenRouter's documented base is .../api/v1; a missing /v1 404s on every call.
    base = os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1").strip().rstrip("/")
    if not base.endswith("/v1"):
        base += "/v1"
    return ChatOpenAI(
        model=model,
        base_url=base,
        api_key=key,
        temperature=0,
        default_headers={
            # both required together for OpenRouter app attribution
            "HTTP-Referer": os.environ.get(
                "APP_REFERER", "https://github.com/tejasvi/pitu-calendar-agent"
            ),
            "X-OpenRouter-Title": os.environ.get("APP_TITLE", "Pitu - Calendar Agent"),
        },
    )


def build_agent(tools: list):
    return create_agent(
        model=build_model(),
        tools=tools,
        system_prompt=SYSTEM_PROMPT,
        middleware=[
            ToolCallLimitMiddleware(
                tool_name="add_calendar_event",
                run_limit=1,  # one create attempt per user request (I4)
                exit_behavior="end",
            )
        ],
    )


def _log_update(chunk: dict[str, Any], session: str, model: str) -> None:
    for node, update in chunk.items():
        if not isinstance(update, dict):
            continue
        msgs = update.get("messages", [])
        if not isinstance(msgs, list):
            msgs = [msgs]
        for m in msgs:
            name = type(m).__name__
            tool_calls = getattr(m, "tool_calls", None) or []
            content = getattr(m, "content", "") or ""
            if tool_calls:
                for tc in tool_calls:
                    print(f"  [{node}] {name} → CALL {tc.get('name')} args={tc.get('args')}", flush=True)
                    trace(session, node, kind="tool_call", model=model,
                          tool=tc.get("name"), args=tc.get("args"))
            else:
                preview = content if len(str(content)) < 300 else str(content)[:300] + "..."
                print(f"  [{node}] {name} → {preview!r}", flush=True)
                trace(session, node, kind="message", model=model, preview=preview)


def run(prompt: str, agent=None, session: str | None = None, tz: str = DEFAULT_TZ) -> str:
    session = session or uuid.uuid4().hex[:8]
    agent = agent or build_agent(make_calendar_tools(require_token(), ZoneInfo(tz)))
    trace(session, "run", kind="request", tz=tz, model=os.environ.get("MODEL"))
    print(f"Thinking... (session {session})", flush=True)
    last: dict[str, Any] | None = None
    for mode, chunk in agent.stream(
        {"messages": [{"role": "user", "content": prompt}]},
        stream_mode=["updates", "values"],
        config={"recursion_limit": 8},
    ):
        if mode == "updates" and isinstance(chunk, dict):
            _log_update(chunk, session, os.environ.get("MODEL", ""))
        elif mode == "values" and isinstance(chunk, dict):
            last = chunk
    reply = ""
    if last:
        messages = last.get("messages") or []
        if messages:
            content = getattr(messages[-1], "content", "")
            reply = content if isinstance(content, str) else str(content)
    trace(session, "run", kind="reply", outcome=reply[:20])
    return reply


def main() -> None:
    tz = os.environ.get("DEFAULT_TZ", DEFAULT_TZ)
    if len(sys.argv) > 1:
        request = " ".join(sys.argv[1:])
    else:
        request = input("Request: ").strip()
    if not request:
        sys.exit(1)
    dated = f"Today is {datetime.now(ZoneInfo(tz)).strftime('%Y-%m-%d %H:%M:%S %Z')}.\nRequest: {request}"
    try:
        print(run(dated, tz=tz))
    except Exception as e:
        print(f"Error: {type(e).__name__}: {e}")


if __name__ == "__main__":
    main()
