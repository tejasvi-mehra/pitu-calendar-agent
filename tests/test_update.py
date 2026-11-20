from zoneinfo import ZoneInfo

from tools import make_calendar_tools


class FakeService:
    def __init__(self, event):
        self.event = event
        self.patched = None
        self.kwargs = None

    def events(self):
        fake = self

        class Events:
            def get(self, **kw):
                return Req(fake.event)

            def patch(self, **kw):
                fake.patched, fake.kwargs = kw["body"], kw
                merged = {**fake.event, **kw["body"]}
                return Req(merged)
        return Events()


class Req:
    def __init__(self, data):
        self.data = data

    def execute(self):
        return self.data


EVENT = {
    "id": "evt1",
    "summary": "Meeting",
    "start": {"dateTime": "2026-11-20T17:00:00+08:00"},
    "end": {"dateTime": "2026-11-20T17:30:00+08:00"},
    "attendees": [{"email": "a@x.com"}],
}


def tool(monkeypatch, svc):
    monkeypatch.setattr("tools.get_calendar_service", lambda *a, **k: svc)
    return {t.name: t for t in make_calendar_tools("fake", ZoneInfo("Asia/Singapore"))}


def test_update_adds_guest_and_keeps_existing(monkeypatch):
    svc = FakeService(dict(EVENT))
    tools = tool(monkeypatch, svc)
    out = tools["update_calendar_event"].invoke({"event_id": "evt1", "add_attendees": "B@Y.com"})
    assert out.startswith("Updated 'Meeting'")
    emails = [a["email"] for a in svc.patched["attendees"]]
    assert emails == ["a@x.com", "b@y.com"]


def test_update_sends_invites_when_guests_change(monkeypatch):
    svc = FakeService(dict(EVENT))
    tools = tool(monkeypatch, svc)
    tools["update_calendar_event"].invoke({"event_id": "evt1", "add_attendees": "b@y.com"})
    assert svc.kwargs["sendUpdates"] == "all"


def test_update_touches_only_given_fields(monkeypatch):
    svc = FakeService(dict(EVENT))
    tools = tool(monkeypatch, svc)
    tools["update_calendar_event"].invoke({"event_id": "evt1", "title": "Renamed"})
    assert set(svc.patched) == {"summary"}


def test_update_retime_keeps_duration(monkeypatch):
    svc = FakeService(dict(EVENT))
    tools = tool(monkeypatch, svc)
    tools["update_calendar_event"].invoke({"event_id": "evt1", "hour": 9})
    start = svc.patched["start"]["dateTime"]
    end = svc.patched["end"]["dateTime"]
    assert start.startswith("2026-11-20T09:00")
    assert end.startswith("2026-11-20T09:30")


def test_update_with_no_fields_is_a_noop(monkeypatch):
    svc = FakeService(dict(EVENT))
    tools = tool(monkeypatch, svc)
    out = tools["update_calendar_event"].invoke({"event_id": "evt1"})
    assert out.startswith("Nothing to update")
    assert svc.patched is None


def test_update_failure_is_a_string(monkeypatch):
    class Broken:
        def events(self):
            raise RuntimeError("boom")

    tools = tool(monkeypatch, Broken())
    out = tools["update_calendar_event"].invoke({"event_id": "evt1", "title": "X"})
    assert out.startswith("Failed to update event")


def test_no_token_in_any_schema(monkeypatch):
    tools = tool(monkeypatch, FakeService(dict(EVENT)))
    for t in tools.values():
        s = t.args_schema.model_json_schema()
        assert "token" not in str(s).lower()
