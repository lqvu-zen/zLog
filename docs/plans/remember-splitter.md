# Plan: Remember splitter sizes

- **Status:** Done
- **Owner:** unassigned
- **Created:** 2026-07-11
- **Related:** ROADMAP v1.4 "Reading & analysis", [settings-persistence.md](settings-persistence.md),
  [detail-pane.md](detail-pane.md)

## Goal

After this ships, the log/detail splitter position is remembered across launches —
resize the detail pane once and it stays where you put it.

## Design

Mirror the existing window-geometry persistence exactly, using
`QSplitter.saveState()`/`restoreState()` (base64), which restores reliably
regardless of show/layout timing.

| File | Layer | Change |
|---|---|---|
| `src/zlog/core/settings.py` | core | Add `"splitter_state": ""` to DEFAULTS. |
| `src/zlog/ui/main_window.py` | ui | `set_splitter_state(v)` restores from base64; settings spec `("splitter_state", getter=base64 of saveState, set_splitter_state)`. The splitter exists (built in `_build_layout`) before settings restore. |
| `tests/test_main_window_settings.py` | tests | The `splitter_state` getter returns a base64 string and the setter round-trips it without error. |

## Architecture touch points

- **Declarative settings parity** preserved (new DEFAULTS key + matching spec).
- **Same pattern as `geometry`** — no new mechanism.

## Verification

- [ ] `uv run pytest`
- [ ] `uv run ruff check .` and `uv run ruff format --check .`
- [ ] Manual: resize the detail pane, relaunch — it's remembered.
