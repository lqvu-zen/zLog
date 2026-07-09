# Plan: Selectable log buffers

- **Status:** Done
- **Owner:** Vũ
- **Created:** 2026-07-09
- **Related:** ROADMAP v1.2 (Capture & scale)

## Goal

Let the user choose which `adb logcat` buffers to stream (main/system/crash/radio/
events/kernel) via **View → Log buffers**, applied on the next Start; persisted.

## Scope

- **In:** a pure `build_logcat_command(adb_path, serial, buffers)`; an `AdbReader`
  `buffers` param; a checkable **Log buffers** submenu; a `log_buffers` setting.
- **Out:** changing buffers live mid-stream (applies on next Start); buffer size (`-G`).

## Design

| File | Change |
|---|---|
| `src/zlog/adb/reader.py` | Extract `build_logcat_command(...)` (pure, testable) adding `-b <buf>` per selected buffer; `AdbReader(buffers=...)` uses it. Default (none) = adb's default buffers, so behavior is unchanged. |
| `tests/test_reader.py` (new) | Unit-test the command builder (default, serial, buffers, bad names dropped). |
| `src/zlog/core/settings.py` | Add `"log_buffers": []`. |
| `src/zlog/ui/main_window.py` | View → **Log buffers** checkable submenu; `start()` passes the checked buffers; persisted via the settings spec. |

## Verification

- [ ] `uv run pytest` (command-builder tests + settings round-trip)
- [ ] `uv run ruff check .` / `format --check`
