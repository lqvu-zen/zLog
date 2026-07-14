# Plan: Fixed column widths with middle-elision

- **Status:** Done
- **Owner:** unassigned
- **Created:** 2026-07-14
- **Related:** [auto-size-columns.md](auto-size-columns.md), [process-name-column.md](process-name-column.md)

## Problem

Auto-sizing the metadata columns made widths shift between views and shrank the
Time column, which hurt readability. The user wants fixed, predictable widths per
column, with long values truncated in the **middle** (keeping both ends legible,
e.g. `vendor.xia….0-service`), and the Time column kept comfortably wide.

## Fix

Revert the model's width tracking; the delegate paints fixed monospace widths and
middle-elides the Tag and Process columns.

- Time `24` (full `YYYY-MM-DD HH:MM:SS.mmm`, not shrunk), PID-TID `12`, Tag `22`
  (middle-elide), Process `30` (middle-elide). Level stays a 1-char chip.
- `seg()` gains a `elide="middle"` mode (Qt.ElideMiddle).
- The model keeps only PID→name resolution (`_pid_names`, `merge_process_names`,
  `PROCESS_ROLE`); the auto-width getters/measurement were removed.

## Verification

- [x] `uv run pytest` (237)
- [x] ruff clean
- [x] middle-elision renders `vendor.xia….0-service`; Time shows the full stamp.
