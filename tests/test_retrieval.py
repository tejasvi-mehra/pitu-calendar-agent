"""The notes agent is read-only and never sees a token (I10)."""

from pathlib import Path

import retrieval


class StubModel:
    def __init__(self, reply: str):
        self.reply = reply
        self.calls = []

    def invoke(self, messages):
        self.calls.append(messages)

        class R:
            content = self.reply

        return R()


def _corpus(tmp_path: Path) -> Path:
    (tmp_path / "a.md").write_text("# Launch\nWe moved launch to 12 October.\n")
    (tmp_path / "b.md").write_text("# Hiring\nTwo backend hires in Q4.\n")
    return tmp_path


def test_load_notes_reads_every_file(tmp_path):
    notes = retrieval.load_notes(_corpus(tmp_path))
    assert set(notes) == {"a.md", "b.md"}


def test_empty_corpus_returns_sentinel(tmp_path):
    assert retrieval.search_notes("anything", tmp_path, StubModel("x")) == "NO_RELEVANT_NOTES"


def test_index_has_one_line_per_note(tmp_path):
    index = retrieval.build_index(retrieval.load_notes(_corpus(tmp_path)))
    assert index.count("\n") == 1
    assert "a.md" in index and "b.md" in index


def test_valid_citation_passes_through(tmp_path):
    model = StubModel("a.md: We moved launch to 12 October.")
    out = retrieval.search_notes("when is the launch", _corpus(tmp_path), model)
    assert out == "a.md: We moved launch to 12 October."


def test_hallucinated_file_is_dropped(tmp_path):
    model = StubModel("c.md: invented fact")
    assert retrieval.search_notes("launch", _corpus(tmp_path), model) == "NO_RELEVANT_NOTES"


def test_no_relevant_notes_reply_is_honoured(tmp_path):
    model = StubModel("NO_RELEVANT_NOTES")
    assert retrieval.search_notes("lunch order", _corpus(tmp_path), model) == "NO_RELEVANT_NOTES"


def test_agent_only_ever_sees_note_text(tmp_path):
    model = StubModel("a.md: We moved launch to 12 October.")
    retrieval.search_notes("launch", _corpus(tmp_path), model)
    payload = str(model.calls)
    assert "ya29" not in payload
    assert "add_calendar_event" not in payload


def test_module_has_no_calendar_tools():
    src = Path(retrieval.__file__).read_text()
    assert "make_calendar_tools" not in src
    assert "add_calendar_event" not in src
