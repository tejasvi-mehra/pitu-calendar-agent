import json

import pytest

from tools import build_rrule, coerce_bool, make_calendar_tools, parse_date_only


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("2026-07-16", "2026-07-16"),
        ("2026-07-16 17:00:00 +08", "2026-07-16"),
        ("  2026-07-16  ", "2026-07-16"),
    ],
)
def test_parse_date_ok(raw, expected):
    assert parse_date_only(raw) == expected


@pytest.mark.parametrize("raw", ["16-07-2026", "tomorrow", ""])
def test_parse_date_bad(raw):
    with pytest.raises(ValueError):
        parse_date_only(raw)


@pytest.mark.parametrize(
    "raw,expected",
    [(True, True), (False, False), ("yes", True), ("Y", True), ("true", True),
     ("1", True), ("no", False), ("false", False), ("", False), ("0", False)],
)
def test_coerce_bool(raw, expected):
    assert coerce_bool(raw) is expected


@pytest.mark.parametrize(
    "args,expected",
    [
        (("", 1, 0, "", ""), None),
        (("daily", 1, 0, "", ""), "RRULE:FREQ=DAILY"),
        (("WEEKLY", 2, 0, "", "MO,WE"), "RRULE:FREQ=WEEKLY;INTERVAL=2;BYDAY=MO,WE"),
        (("weekly", 1, 8, "", ""), "RRULE:FREQ=WEEKLY;COUNT=8"),
        (("WEEKLY", 1, 0, "2026-12-22", ""), "RRULE:FREQ=WEEKLY;UNTIL=20261222T235959Z"),
        (("WEEKLY", 1, 8, "2026-12-22", ""), "RRULE:FREQ=WEEKLY;COUNT=8"),
    ],
)
def test_build_rrule(args, expected):
    assert build_rrule(*args) == expected


def test_build_rrule_rejects_bad_freq():
    with pytest.raises(ValueError):
        build_rrule("FORTNIGHTLY", 1, 0, "", "")


class FakeService:
    """Stands in for googleapiclient; records the body it was asked to insert."""

    def __init__(self):
        self.body = None
        self.kwargs = None

    def events(self):
        fake = self

        class Events:
            def insert(self, **kwargs):
                fake.body, fake.kwargs = kwargs["body"], kwargs

                class Req:
                    def execute(_self):
                        return {
                            "id": "evt_1",
                            "summary": kwargs["body"]["summary"],
                            "start": kwargs["body"]["start"],
                            "end": kwargs["body"]["end"],
                            "hangoutLink": "https://meet.example/abc",
                        }
                return Req()
        return Events()


def _tool(monkeypatch, svc, tz="Europe/London"):
    from zoneinfo import ZoneInfo
    monkeypatch.setattr("tools.get_calendar_service", lambda *a, **k: svc)
    return make_calendar_tools("fake-token", ZoneInfo(tz))[0]


def test_tool_creates_event_in_supplied_zone(monkeypatch):
    svc = FakeService()
    tool = _tool(monkeypatch, svc)
    out = tool.invoke({"title": "Lunch", "date": "2026-11-20", "hour": 13,
                       "attendees": "a@x.com, A@X.com , b@y.com", "create_meet": "yes"})
    assert out.startswith("Created 'Lunch'")
    assert svc.body["start"]["timeZone"] == "Europe/London"
    assert [a["email"] for a in svc.body["attendees"]] == ["a@x.com", "b@y.com"]
    assert svc.kwargs["conferenceDataVersion"] == 1
    assert "meet=https://meet.example/abc" in out


def test_tool_failure_is_a_string_not_an_exception(monkeypatch):
    class Broken:
        def events(self):
            raise RuntimeError("boom")
    tool = _tool(monkeypatch, Broken())
    out = tool.invoke({"title": "X", "date": "2026-11-20", "hour": 9})
    assert out.startswith("Failed to create event")
    assert "Created" not in out


def test_build_model_rejects_bad_key(monkeypatch):
    import pitu_agent
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.setenv("MODEL", "x/y")
    with pytest.raises(RuntimeError, match="OPENROUTER_API_KEY is empty"):
        pitu_agent.build_model()
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-proj-not-openrouter")
    with pytest.raises(RuntimeError, match="must be an OpenRouter key"):
        pitu_agent.build_model()


def test_build_model_uses_documented_headers(monkeypatch):
    import pitu_agent
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")
    monkeypatch.setenv("MODEL", "inclusionai/ling-3.2-flash:free")
    model = pitu_agent.build_model()
    headers = model.default_headers
    assert "X-OpenRouter-Title" in headers
    assert "HTTP-Referer" in headers
    assert model.model_name == "inclusionai/ling-3.2-flash:free"


def test_build_model_normalizes_base_url(monkeypatch):
    import pitu_agent
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")
    monkeypatch.setenv("MODEL", "inclusionai/ling-3.2-flash:free")
    for raw in ("https://openrouter.ai/api", "https://openrouter.ai/api/", "https://openrouter.ai/api/v1"):
        monkeypatch.setenv("OPENROUTER_BASE_URL", raw)
        assert pitu_agent.build_model().openai_api_base == "https://openrouter.ai/api/v1"


def test_no_token_in_tool_schema():
    from zoneinfo import ZoneInfo
    tool = make_calendar_tools("fake-token", ZoneInfo("UTC"))[0]
    props = tool.args_schema.model_json_schema()["properties"]
    assert "token" not in json.dumps(props).lower()
