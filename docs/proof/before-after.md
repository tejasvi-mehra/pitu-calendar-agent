# Before / after

Baseline measured at Phase 0, 2026-11-19, before any feature work.

| Metric | Before | After |
|---|---|---|
| Import/runtime bugs | 1 (`agents.py` imported `fetch_text_from_url`, which does not exist) | 0 |
| Dead files | 2 (`agents.py`, `add_event.py`) | 0 |
| Tests collected | 0 (pytest not installed) | 76 Python + 9 Vitest |
| Contract eval pass rate | n/a (no harness) | 10/10 |
| Live eval pass rate | n/a | 4/4 on `nvidia/nemotron-3.5-super-vl:free` |
| Tools exposed over MCP | 0 | 5 |
| Timezone definitions in source | 2 (`prompt.py`, `pitu_agent.py`) | 1 (`tools.py` default) |
| Secret files tracked in repo | 2 (`credentials.json`, `token.json`), untracked but unguarded | 0 |
| Google credential code on server | 2 functions doing interactive OAuth | 0 |
| Invariants covered by test | 0 / 10 | 10 / 10 |
| Booking works via | CLI (stub tool) | CLI, MCP, notes retrieval, HTTP, browser |

"How measured" commands are in SPEC.md section 10. Do not edit the "before" column.
