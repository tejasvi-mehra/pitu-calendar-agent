"""Security regressions. Each test corresponds to a way this service could be abused."""

import os

import pytest
from fastapi.testclient import TestClient

os.environ["GOOGLE_CLIENT_ID"] = "test-client.apps.googleusercontent.com"
os.environ["ALLOWED_EMAILS"] = "me@example.com"
os.environ["RATE_LIMIT_PER_MIN"] = "3"

import server  # noqa: E402

client = TestClient(server.app)


class R:
    status_code = 200

    def __init__(self, body):
        self.body = body

    def json(self):
        return self.body


def fake_tokeninfo(monkeypatch, **over):
    body = {
        "aud": os.environ["GOOGLE_CLIENT_ID"],
        "email": "me@example.com",
        "scope": "https://www.googleapis.com/auth/calendar.events",
    }
    body.update(over)

    async def get(self, url, params=None):
        return R(body)

    monkeypatch.setattr("httpx.AsyncClient.get", get)


@pytest.fixture(autouse=True)
def reset():
    server._rl.clear()
    yield
    server._rl.clear()


def test_empty_allowlist_denies_everyone(monkeypatch):
    """An unset ALLOWED_EMAILS must lock out, never open up."""
    fake_tokeninfo(monkeypatch)
    monkeypatch.setenv("ALLOWED_EMAILS", "")
    r = client.post("/chat", json={"text": "hi"}, headers={"Authorization": "Bearer ya29.x"})
    assert r.status_code == 403


def test_case_insensitive_allowlist(monkeypatch):
    fake_tokeninfo(monkeypatch, email="ME@Example.COM")
    async def run(*a, **k):
        return "ok"

    monkeypatch.setattr(server.pitu_agent, "run", run)
    r = client.post("/chat", json={"text": "hi"}, headers={"Authorization": "Bearer ya29.x"})
    assert r.status_code == 200


def test_empty_bearer_is_401(monkeypatch):
    fake_tokeninfo(monkeypatch)
    r = client.post("/chat", json={"text": "hi"}, headers={"Authorization": "Bearer"})
    assert r.status_code == 401


def test_path_traversal_on_public_assets_is_404():
    for path in ("/../.env", "/..%2F..%2Fetc%2Fpasswd.png", "/server.py"):
        r = client.get(path)
        assert r.status_code == 404, path
        assert "OPENROUTER" not in r.text


def test_asset_path_traversal_blocked():
    r = client.get("/assets/../../server.py")
    assert r.status_code == 404


def test_rate_limit_is_per_account_not_global(monkeypatch):
    fake_tokeninfo(monkeypatch)

    async def run(*a, **k):
        return "ok"

    monkeypatch.setattr(server.pitu_agent, "run", run)
    h1 = {"Authorization": "Bearer ya29.a"}
    for _ in range(3):
        client.post("/chat", json={"text": "hi"}, headers=h1)
    # a second allowlisted account must still get through
    monkeypatch.setenv("ALLOWED_EMAILS", "me@example.com,other@example.com")
    fake_tokeninfo(monkeypatch, email="other@example.com")
    r = client.post("/chat", json={"text": "hi"}, headers={"Authorization": "Bearer ya29.b"})
    assert r.status_code == 200


def test_rate_state_pruning():
    for i in range(10_001):
        server._rl[f"user{i}@example.com"].append(1.0)
    server._prune_rate_state()
    # nothing is empty, so the guard leaves the table alone rather than dropping live limits
    assert len(server._rl) == 10_001
    server._rl["spent@example.com"].clear()
    server._prune_rate_state()
    assert "spent@example.com" not in server._rl


def test_security_headers_present():
    r = client.get("/health")
    csp = r.headers.get("content-security-policy", "")
    assert "script-src 'self' https://accounts.google.com" in csp
    assert "object-src 'none'" in csp
    assert r.headers.get("x-content-type-options") == "nosniff"
    assert r.headers.get("x-frame-options") == "DENY"


def test_trace_id_comes_from_server_not_client():
    """A client-supplied session id must not let one user read another's trace path."""

    src = open(server.__file__).read()
    assert "uuid.uuid4()" in src
    assert "x-session" not in src.lower()
