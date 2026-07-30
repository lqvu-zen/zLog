# Plan: Persist the last-launched app across sessions

- **Status:** Done  <!-- Draft | Approved | In progress | Done | Abandoned -->
- **Owner:** unassigned
- **Created:** 2026-07-29
- **Related:** [windows-app-focus.md](windows-app-focus.md), [settings-persistence.md](settings-persistence.md)

## Goal

Reopening zLog and picking **Launch App…** prefills the program/arguments/working
directory from the last app you launched, even after restarting zLog — not just
within the same session.

## Why

`self._last_launch` already prefills the **Launch App…** dialog (see
`launch_app()`), but it's a plain instance attribute set in `__init__` to `None`
and never saved — closing zLog forgets it. Every other per-session convenience
(last device, recent files, search history, …) already goes through the
declarative settings table in `_settings_specs()`; this one was simply missed.

## Scope

- **In:** add a `last_launch` key to `core/settings.DEFAULTS` and a matching row
  in `MainWindow._settings_specs()`, storing `{exe, args, cwd}`.
- **Out (non-goals):** a "recent launches" list (just the one most-recent entry,
  matching current in-session behavior); changing `launch_app()`'s own logic.

## Design

| File | Layer | Change |
|---|---|---|
| `src/zlog/core/settings.py` | core | New `DEFAULTS["last_launch"] = {"exe": "", "args": "", "cwd": ""}`. |
| `src/zlog/ui/main_window.py` | ui | New spec row `("last_launch", get_last_launch, set_last_launch)`: `get` reads `self._last_launch` (or the empty dict if `None`) into that shape; `set` reads it back into `self._last_launch` as a tuple, leaving `None` when `exe` is empty (matches the untouched default `launch_app()` already handles). |
| `tests/test_main_window_settings.py` | tests | Extend `test_settings_round_trip` with a launch + reload assertion. |

## Architecture touch points

None — pure settings persistence, same JSON file, no threading/model changes.

## Risks & regressions to check

- `_settings_specs()` asserts its key set matches `DEFAULTS` exactly — both files
  must be updated together or the app fails to start.
- An empty/never-launched state (`self._last_launch is None`) must round-trip
  cleanly (saves as the all-empty dict, loads back to `None`, not a dict of blanks
  that `launch_app()` would misread as a real prior launch).

## Verification

- [x] Targeted tests: `tests/test_settings.py` (6 passed), `tests/test_main_window_settings.py`
      + `tests/test_app_focus.py` (84 passed) — full suite deferred to the batched QA pass
- [x] `uv run ruff check .` and `uv run ruff format --check .`

## Open questions

None.
