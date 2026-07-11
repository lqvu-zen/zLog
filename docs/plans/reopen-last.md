# Plan: Reopen last log on launch

- **Status:** Done
- **Owner:** unassigned
- **Created:** 2026-07-11
- **Related:** ROADMAP v1.3 "Sessions & export", [open-recent.md](open-recent.md)

## Goal

After this ships, an opt-in **View → Reopen Last Log on Launch** toggle makes zLog
reopen the most-recent log automatically at startup, so you land back where you
left off. Off by default (auto-loading a big file surprises people otherwise).

## Scope

- **In:** a checkable View action + `reopen_last` setting; on launch, if enabled
  and a recent log exists (and we're not streaming), load `_recent[0]`.
- **Out:** restoring filters/bookmarks (that's session bundles), reopening a live
  stream, choosing which recent to reopen.

## Design

| File | Layer | Change |
|---|---|---|
| `src/zlog/core/settings.py` | core | Add `"reopen_last": False` to DEFAULTS. |
| `src/zlog/ui/main_window.py` | ui | Add a checkable `reopen_last_action` in the View menu (after Clear on Start). Add `_maybe_reopen_last()` — if checked and `_recent` non-empty and `reader is None`, `_load_log_file(_recent[0])`; call it at the end of `__init__` (after settings restore). Settings spec `("reopen_last", isChecked, setChecked)`. |
| `tests/test_main_window_settings.py` | tests | With the toggle on and a recent temp log, `_maybe_reopen_last` loads it; with the toggle off, it's a no-op. |

## Architecture touch points

- **Reuses `_load_log_file` + `_recent`** from Open Recent; no new load path.
- **Declarative settings parity** preserved (new DEFAULTS key has a matching spec).

## Risks & regressions to check

- **Missing file:** `_load_log_file` already reports + forgets a gone path, so a
  stale last-log degrades gracefully.
- **Order:** must run after `_load_and_apply_settings` so `_recent` and the toggle
  are restored first.

## Verification

- [ ] `uv run pytest`
- [ ] `uv run ruff check .` and `uv run ruff format --check .`
- [ ] Manual: enable, reopen a log, relaunch — it comes back.
