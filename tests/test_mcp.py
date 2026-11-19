"""Tool schemas must survive the MCP round trip, and no token may appear in them (I3)."""

import asyncio
import json
import os

import pytest

import pitu_agent


@pytest.fixture(scope="module")
def tools():
    os.environ.setdefault("GOOGLE_TOKEN", "fake-token-for-schema-test")
    client = pitu_agent.mcp_client("fake-token-for-schema-test", "Asia/Singapore")
    yield asyncio.run(client.get_tools())


def test_both_tools_come_over_mcp(tools):
    names = sorted(t.name for t in tools)
    assert names == ["add_calendar_event", "delete_calendar_event", "list_calendar_events", "search_notes", "update_calendar_event"]


def _schema(t) -> dict:
    s = t.args_schema
    return s if isinstance(s, dict) else s.model_json_schema()


def test_no_token_parameter_in_any_schema(tools):
    for t in tools:
        assert "token" not in json.dumps(_schema(t)).lower(), f"{t.name} leaks a token parameter"


def test_create_schema_keeps_its_fields(tools):
    create = next(t for t in tools if t.name == "add_calendar_event")
    props = _schema(create)["properties"]
    for field in ("title", "date", "hour", "attendees", "create_meet", "freq"):
        assert field in props


def test_agent_has_no_direct_tool_import():
    src = open(pitu_agent.__file__).read()
    assert "from tools import add_calendar_event" not in src
    assert "make_calendar_tools" not in src
