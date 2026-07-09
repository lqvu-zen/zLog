# Plan: Clear the device log buffer

- **Status:** Done
- **Owner:** Vũ
- **Created:** 2026-07-09
- **Related:** ROADMAP v1.2 (Capture & scale), log-buffers.md

## Goal

A **View → Clear device log buffer** action that runs `adb logcat -c` to wipe the
device's on-device ring buffer, so a fresh stream starts clean.

## Scope

- **In:** `adb.packages.clear_logcat(serial)`; a View menu action routed through the
  existing `_run_adb` guard; a status message.
- **Out:** clearing the app's own view (that's the ✕ button); buffer sizing.

## Design

| File | Change |
|---|---|
| `src/zlog/adb/packages.py` | `clear_logcat(serial, adb_path, timeout)` → runs `adb [-s serial] logcat -c` (check=True), returns True. |
| `tests/test_adb_clear.py` (new) | Monkeypatch `subprocess.run` to assert the built argv. |
| `src/zlog/ui/main_window.py` | View action `_clear_device_buffer()` → needs a selected device; uses `_run_adb`. |

## Verification

- [ ] `uv run pytest` (command argv + no-device path)
- [ ] `uv run ruff check .` / `format --check`
