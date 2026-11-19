"""Pitu MCP server over stdio.

The access token arrives in the environment at spawn time, never as a tool argument,
so it cannot appear in model output (I3). Run standalone for the inspector:

    mcp dev mcp_server.py
"""

import os
from zoneinfo import ZoneInfo

from mcp.server.fastmcp import FastMCP

from retrieval import search_notes
from tools import DEFAULT_TZ, make_calendar_tools

mcp = FastMCP("pitu-calendar")

_TOKEN = os.environ.get("GOOGLE_TOKEN", "")
_TZ = ZoneInfo(os.environ.get("CALENDAR_TZ", DEFAULT_TZ))

for t in make_calendar_tools(_TOKEN, _TZ):
    # hand MCP the plain function so it can introspect the real signature
    mcp.add_tool(t.func, name=t.name, description=t.description)

# read-only, no calendar tools, no token (I10). Only `question` is exposed: the model
# must not choose the notes path or the model used for selection.
def notes_lookup(question: str) -> str:
    """Search meeting notes for facts, decisions and follow-ups.
    Returns 'file: excerpt' lines, or NO_RELEVANT_NOTES. Cite the returned file.
    Args:
        question: What to look up in the notes.
    """
    return search_notes(question)


mcp.add_tool(notes_lookup, name="search_notes")

if __name__ == "__main__":
    mcp.run()
