# Plan: Capture dumpsys snapshot

- **Status:** Done
- **Owner:** unassigned
- **Created:** 2026-07-20
- **Related:** save-load.md, adb-connect-wifi.md

## Goal

File → **Capture dumpsys…** saves a one-shot `adb shell dumpsys` snapshot (all
services, or a single one like `battery`/`meminfo`) to a text file for context.

## Design

| File | Layer | Change |
|---|---|---|
| `src/zlog/core/snapshot.py` (new) | core | `dumpsys_args(section) -> list[str]` — pure argv builder; blank = full dump, else first token as the service (no injection). Unit-tested. |
| `src/zlog/adb/snapshot.py` (new) | adb | `capture_dumpsys(serial, section, adb_path, timeout)` runs the one-shot call, returns stdout. |
| `src/zlog/ui/main_window.py` | ui | File → Capture dumpsys…: prompt for a service (blank = all), run via `_run_adb`, save via QFileDialog. |

## Verification
- [x] `uv run pytest tests/test_snapshot.py`
- [x] `uv run ruff check .` / `format --check`
