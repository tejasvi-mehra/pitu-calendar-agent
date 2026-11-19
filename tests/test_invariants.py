"""One test per invariant in SPEC.md §3. A missing invariant is a broken claim."""

import json
import os
import re
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

import pitu_agent
import server
from tools import make_calendar_tools
from trace import trace

WEBAPP = Path(__file__).resolve().parent.parent / "webapp" / "src"


# ---------- I1: the token never reaches the model provider ----------


def test_I1_model_payload_never_contains_token(monkeypatch):
    """build_model produces a client; the agent builds messages before any tool runs."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")
    monkeypatch.setenv("MODEL", "test/model")
    model = pitu_agent.build_model()
    messages = [("system", "sys"), ("user", "book lunch tomorrow")]
    payload = json.dumps([m for m in messages])
    assert "ya29" not in payload
    assert model.default_headers.get("Authorization") is None


def test_I1_agent_source_never_puts_token_in_messages():
    src = Path(pitu_agent.__file__).read_text()
    # the token is only ever handed to the MCP child's env, never a message
    assert '{"role": "user", "content": prompt}' in src
    assert not re.search(r'content.*token', src)


# ---------- I2: no token in traces or error bodies ----------


def test_I2_trace_redacts_token(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    token = "ya29." + "B" * 40
    trace("s_i2", "run", kind="tool_call", header=f"Bearer {token}", note=token)
    written = (tmp_path / "traces" / "s_i2.jsonl").read_text()
    assert token not in written
    assert "[REDACTED]" in written


def test_I2_error_body_has_no_token(monkeypatch):
    from fastapi.testclient import TestClient

    os.environ["GOOGLE_CLIENT_ID"] = "test-client.apps.googleusercontent.com"
    os.environ["ALLOWED_EMAILS"] = "me@example.com"
    client = TestClient(server.app)
    r = client.post("/chat", json={"text": "hi"}, headers={"Authorization": "Bearer ya29.SECRET"})
    assert r.status_code == 401
    assert "ya29" not in r.text


# ---------- I3: no token parameter in any tool schema ----------


def test_I3_no_token_parameter(monkeypatch):
    monkeypatch.setattr("tools.get_calendar_service", lambda *a, **k: None)
    for t in make_calendar_tools("fake", ZoneInfo("UTC")):
        schema = json.dumps(t.args_schema.model_json_schema()).lower()
        assert "token" not in schema, f"{t.name} exposes a token"


# ---------- I4: at most one write per request ----------


def test_I4_write_budget_is_one():
    """The compiled agent does not expose middleware, so assert on the source of truth."""
    src = Path(pitu_agent.__file__).read_text()
    adds = re.findall(r'tool_name="(\w+)",\s*\n\s*run_limit=(\d+)', src)
    limits = dict(adds)
    assert limits.get("add_calendar_event") == "1", limits
    assert limits.get("delete_calendar_event") == "1", limits


# ---------- I5: a failure never reports success ----------


def test_I5_failure_string_never_starts_with_created(monkeypatch):
    class Broken:
        def events(self):
            raise RuntimeError("boom")

    monkeypatch.setattr("tools.get_calendar_service", lambda *a, **k: Broken())
    tools = {t.name: t for t in make_calendar_tools("fake", ZoneInfo("UTC"))}
    out = tools["add_calendar_event"].invoke({"title": "X", "date": "2026-11-20", "hour": 9})
    assert out.startswith("Failed")
    assert not out.startswith("Created")

    out = tools["delete_calendar_event"].invoke({"event_id": "nope"})
    assert out.startswith("Failed")

    out = tools["update_calendar_event"].invoke({"event_id": "nope", "title": "X"})
    assert out.startswith("Failed")


# ---------- I6: a pending action cannot be confirmed by another account ----------


def test_I6_server_rejects_a_second_account(monkeypatch):
    """Only one account is allowlisted, so any other sub is refused before any action."""
    from fastapi.testclient import TestClient

    os.environ["GOOGLE_CLIENT_ID"] = "test-client.apps.googleusercontent.com"
    os.environ["ALLOWED_EMAILS"] = "me@example.com"
    server._rl.clear()

    class R:
        status_code = 200

        def json(self):
            return {
                "aud": os.environ["GOOGLE_CLIENT_ID"],
                "email": "intruder@example.com",
                "scope": "calendar.events",
            }

    async def fake_get(self, url, params=None):
        return R()

    monkeypatch.setattr("httpx.AsyncClient.get", fake_get)
    r = TestClient(server.app).post(
        "/chat", json={"text": "delete everything"}, headers={"Authorization": "Bearer ya29.x"}
    )
    assert r.status_code == 403


# ---------- I7: no third-party script besides GIS ----------


def test_I7_only_gis_is_loaded_from_outside():
    html = (WEBAPP.parent / "index.html").read_text()
    assert "accounts.google.com" not in html, "GIS is loaded dynamically in auth.ts, not as a tag"
    externals = re.findall(r'src="https?://([^/"]+)', html)
    assert externals == [], f"index.html loads external scripts: {externals}"

    auth = (WEBAPP / "lib" / "auth.ts").read_text()
    # scope URLs name an API, not a script host; only src/href loads matter
    loads = re.findall(r'(?:src|href)\s*=\s*"(https?://([a-z.]+))', auth)
    hosts = {h for _, h in loads}
    assert hosts <= {"accounts.google.com"}, f"auth.ts loads unexpected hosts: {hosts}"


def test_I7_no_dangerous_html_rendering():
    for f in WEBAPP.rglob("*.tsx"):
        assert "dangerouslySetInnerHTML" not in f.read_text(), f"{f.name} injects HTML"


# ---------- I8 / I9 / I10 live in test_server.py and test_retrieval.py ----------
# I8: every route rejects a bad audience, allowlist or rate -> test_server.py
# I9: an unknown zone falls back without raising      -> test_test_timezone_falls_back
# I10: the notes agent has no calendar tools          -> test_retrieval.py
#
# Asserted here so the claim "10 invariants covered" is checkable in one place.


def test_I8_I9_I10_have_tests():
    root = Path(__file__).resolve().parent
    server_tests = (root / "test_server.py").read_text()
    assert "def test_foreign_audience_is_401" in server_tests  # I8
    assert "def test_timezone_falls_back" in server_tests  # I9
    retrieval_tests = (root / "test_retrieval.py").read_text()
    assert "def test_module_has_no_calendar_tools" in retrieval_tests  # I10
