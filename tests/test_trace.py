import json


from trace import redact, trace


def test_redact_token_shapes():
    for raw in ["ya29.a0AfH6SMB", "Bearer abc123", "sk-or-v1-deadbeef"]:
        assert "[REDACTED]" in redact(f"prefix {raw} suffix")


def test_redact_walks_structures():
    out = redact({"args": {"note": "ya29.secret"}, "list": ["Bearer x"]})
    assert "ya29" not in json.dumps(out)
    assert "Bearer" not in json.dumps(out)


def test_trace_never_writes_a_token(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    token = "ya29." + "A" * 40
    trace("s1", "run", kind="tool_call", args={"attendees": "a@x.com"}, header=f"Bearer {token}")
    written = (tmp_path / "traces" / "s1.jsonl").read_text()
    assert token not in written
    assert "a@x.com" in written
