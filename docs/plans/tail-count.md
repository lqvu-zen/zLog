# Plan: Start-from-tail (recent N lines)

- **Status:** Done
- **Owner:** Vũ
- **Created:** 2026-07-09
- **Related:** ROADMAP v1.2, log-buffers.md

## Goal

Let the user start streaming from the most recent **N** lines (`adb logcat -T N`)
instead of the whole buffer — faster start, less noise. Persisted; applies on Start.

## Scope

- **In:** `build_logcat_command(..., tail)`; `AdbReader(tail=...)`; a **View → Start
  from** exclusive submenu (Whole buffer / 500 / 1000 / 5000); a `tail_count` setting.
- **Out:** dump-and-exit mode (`-t`); live change of the count mid-stream.

## Design

| File | Change |
|---|---|
| `src/zlog/adb/reader.py` | `build_logcat_command` gains `tail=0`; adds `-T <n>` when `tail > 0`. `AdbReader(tail=...)`. |
| `tests/test_reader.py` | Cover `tail` in the argv. |
| `src/zlog/core/settings.py` | Add `"tail_count": 0`. |
| `src/zlog/ui/main_window.py` | View → **Start from** exclusive submenu; `start()` passes the count; persisted. |

## Verification

- [ ] `uv run pytest` (command builder + settings round-trip)
- [ ] `uv run ruff check .` / `format --check`
