# Plan: Auto-size the metadata columns to maximize the message area

- **Status:** Superseded by [fixed-columns-middle-elide.md](fixed-columns-middle-elide.md)
- **Owner:** unassigned
- **Created:** 2026-07-14
- **Related:** [ui-column-polish.md](ui-column-polish.md), [process-name-column.md](process-name-column.md), [logcat-style-ui.md](logcat-style-ui.md)

## Problem

The delegate painted the Time / PID-TID / Tag columns at fixed monospace widths
(24 / 12 / 22), padded for the worst case (full year time-stamp, long tags). On the
common case (18-char stamp, short tags) that wasted horizontal space and shrank the
message area.

## Fix

Size each metadata column to the widest value actually present, capped and
only-growing (so the layout doesn't thrash). The model tracks the max char length
of `time`, `pid-tid`, `tag` (and already the process name) as rows append; the
delegate reads those widths (with small floors) instead of the fixed constants.

Caps: time 23 (`YYYY-MM-DD HH:MM:SS.mmm`), pid-tid 13, tag 24, process 40.
Floors keep a column from collapsing before data arrives.

| File | Change |
|---|---|
| `ui/log_model.py` | Track `_time_col_chars` / `_pidtid_col_chars` / `_tag_col_chars` in `append_entries`; reset in `clear()`; expose `time_col_chars()` / `pidtid_col_chars()` / `tag_col_chars()`. |
| `ui/log_delegate.py` | Read those widths from the source model (with min floors) instead of `_TIME_W` / `_PIDTID_W` / `_TAG_W`. |

## Verification

- [x] `uv run pytest` (238)
- [x] ruff clean
- [x] no-year log sizes time→18, pid-tid→9, tag→content; year log time→23.
