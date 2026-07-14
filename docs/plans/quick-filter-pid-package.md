# Plan: Right-click quick-filter by PID and package

- **Status:** Done
- **Owner:** unassigned
- **Created:** 2026-07-14
- **Related:** [mute-tag.md](mute-tag.md), [process-name-column.md](process-name-column.md), [package-filter.md](package-filter.md)

## Goal

Right-click a log line → **Filter to… PID <pid>** / **Package <name>**, exactly like
the existing Level and Tag quick-filters.

## Design

Two new query-bar tokens (so it flows through the single query path and persists):

- `pid:<n>` (comma-set `pid:100,200`) — keep only those exact PIDs.
- `proc:<text>` — keep rows whose resolved process/package name contains `<text>`
  (uses the model's pid→name map; works offline too). The menu labels it "Package".

| File | Change |
|---|---|
| `core/query.py` | Parse `pid:` / `proc:` (`process:`); add `pids` + `process` to `QuerySpec`. Pure, tested. |
| `ui/log_model.py` | `LogFilterProxy`: `set_query_pids` (exact-PID gate) + `set_proc` (name gate via `model.process_name`). |
| `ui/main_window.py` | `_apply_query` drives the two gates; `_show_table_menu` adds "PID: <pid>" and "Package: <name>" (when known) to "Filter to…". |
| tests | query parsing; proxy gates; menu tokens. |

## Verification

- [ ] `uv run pytest`  - [ ] ruff clean
- [ ] Right-click a line → Filter to PID / Package narrows the view; clearing the query restores it.
