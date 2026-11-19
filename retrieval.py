"""Retrieval over meeting notes, performed by a read-only agent.

OpenRouter serves chat completions only, so there is no embedding endpoint and no
local model. The notes agent reads the corpus itself and returns cited excerpts.

Read-only by construction: this module never imports a calendar tool and never
receives a Google token (I10).
"""

import os
import re
from pathlib import Path

NOTES_DIR = Path(os.environ.get("NOTES_DIR", "notes"))

_AGENT_PROMPT = """You are a meeting-notes retrieval assistant. You are given a question and a set
of notes. Quote only what appears in the notes. Do not invent facts.

Reply with at most 3 lines, each in this exact form:
<file>: <exact quote from that file>

If the notes contain nothing relevant, reply with exactly: NO_RELEVANT_NOTES"""


def load_notes(notes_dir: Path = NOTES_DIR) -> dict[str, str]:
    """Every note, keyed by file name. Empty dict when the directory is missing."""
    return {p.name: p.read_text() for p in sorted(notes_dir.glob("*.md"))}


def build_index(notes: dict[str, str]) -> str:
    """Titles and first content line per note — enough to choose without sending the corpus."""
    lines = []
    for name, body in notes.items():
        meaningful = [ln.strip() for ln in body.splitlines() if ln.strip() and not ln.startswith("#")]
        first = meaningful[0] if meaningful else ""
        lines.append(f"- {name}: {first[:120]}")
    return "\n".join(lines)


def parse_citations(reply: str, known: set[str]) -> list[tuple[str, str]]:
    """Keep only lines whose file exists in the corpus. Hallucinated files are dropped."""
    out = []
    for line in reply.splitlines():
        if ":" not in line:
            continue
        name, quote = line.split(":", 1)
        name, quote = name.strip().lstrip("-* ").strip(), quote.strip()
        if name in known and quote:
            out.append((name, quote))
    return out


def search_notes(question: str, notes_dir: Path = NOTES_DIR, model=None) -> str:
    """Returns 'file: excerpt' lines, or NO_RELEVANT_NOTES."""
    notes = load_notes(notes_dir)
    if not notes:
        return "NO_RELEVANT_NOTES"

    if model is None:
        from pitu_agent import build_model

        model = build_model(os.environ.get("RESEARCH_MODEL"))

    keywords = set(re.findall(r"[a-z]{4,}", question.lower()))
    candidates = {
        name: body
        for name, body in notes.items()
        if keywords & set(re.findall(r"[a-z]{4,}", body.lower()))
    } or notes

    msg = (
        f"Question: {question}\n\nIndex:\n{build_index(candidates)}\n\n"
        "Notes:\n\n" + "\n\n".join(f"### {n}\n{b}" for n, b in candidates.items())
    )
    reply = model.invoke([("system", _AGENT_PROMPT), ("user", msg)]).content
    reply = reply if isinstance(reply, str) else str(reply)

    cites = parse_citations(reply, set(candidates))
    trace_retrieval(question, candidates, cites)
    if not cites:
        return "NO_RELEVANT_NOTES"
    return "\n".join(f"{name}: {quote}" for name, quote in cites)


def trace_retrieval(question: str, candidates: dict, cites: list) -> None:
    """Record the retrieval step; never the note bodies."""
    from trace import trace

    trace(
        os.environ.get("PITU_SESSION", "retrieval"),
        "retrieval",
        kind="retrieval",
        query=question[:200],
        candidate_files=sorted(candidates),
        cited=[c[0] for c in cites],
        model=os.environ.get("RESEARCH_MODEL") or os.environ.get("MODEL"),
    )
