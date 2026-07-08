# Plan: Relative-time display

- **Status:** Done
- **Owner:** Vũ
- **Created:** 2026-07-08
- **Related:** column-visibility, ui-column-polish

## Goal

Toggle the Time column between the absolute timestamp and elapsed time — either since
capture start or since the previous visible line — to make gaps between events obvious.

## Scope

- **In:** a **View → Time display** submenu (Absolute / Since start / Delta); the model
  renders the Time column per the chosen mode; choice persisted.
- **Out:** changing the underlying stored `LogEntry.time`; per-row absolute+relative
  side by side (one column, one mode).

## Design

Time parsing/formatting is pure and belongs in `core`; the model asks core to format.

| File | Layer | Change |
|---|---|---|
| `src/zlog/core/timefmt.py` (new) | core | `parse_logcat_time(s) -> timedelta|None` and helpers to format elapsed/delta; unit-tested, Qt-free. |
| `src/zlog/ui/log_model.py` | ui | Model holds a `time_mode` + a baseline; `data()` for the Time column formats via core. A mode change emits `dataChanged` for column 0. |
| `src/zlog/ui/main_window.py` | ui | View submenu sets the mode; persisted via the settings spec (`time_mode`). |
| `src/zlog/core/settings.py` | core | Add `"time_mode": "absolute"` to `DEFAULTS`. |

## Architecture touch points

- Logcat threadtime timestamps have no date; deltas assume same-day and handle midnight
  rollover defensively (documented). Baseline = first appended row's time.
- Model stays virtualized; only the Time column's display changes.
- Versioning: no bump.

## Risks & regressions to check

- Unparsed/banner lines (empty time) render blank in relative modes, not a crash.
- Mode switch repaints existing rows (dataChanged) without a full reset.
- Round-trip of `time_mode` through settings; spec-parity assert still holds.

## Verification

- [ ] `uv run pytest` (new core timefmt tests + settings round-trip incl. time_mode)
- [ ] `uv run ruff check .` and `uv run ruff format --check .`
- [ ] Headless: seed timed rows, switch modes, assert formatted strings
