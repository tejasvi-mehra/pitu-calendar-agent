# Before / after

Baseline measured at Phase 0, 2026-11-19, before any feature work.

| Metric | Before | After |
|---|---|---|
| Import/runtime bugs | 1 (`agents.py` imported `fetch_text_from_url`, which does not exist) | — |
| Dead files | 2 (`agents.py`, `add_event.py`) | — |
| Tests collected | 0 (pytest not installed) | — |
| Contract eval pass rate | n/a (no harness) | — |
| Tools exposed over MCP | 0 | — |
| Timezone definitions in source | 2 (`prompt.py`, `pitu_agent.py`) | 1 (`tools.py` default) |
| Secret files tracked in repo | 2 (`credentials.json`, `token.json`), untracked but unguarded | 0 |
| Google credential code on server | 2 functions (`get_google_creds`, `get_calendar_service` doing OAuth) | 0 |
| Invariants covered by test | 0 / 10 | — |

"How measured" commands are in SPEC.md section 10. Do not edit the "before" column.
