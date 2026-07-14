# Plan: Optional process/package-name column (like Android Studio)

- **Status:** Done
- **Owner:** unassigned
- **Created:** 2026-07-14
- **Related:** [package-filter.md](package-filter.md), [live-pid-tracking.md](live-pid-tracking.md), [logcat-style-ui.md](logcat-style-ui.md)

## Problem

`adb logcat -v threadtime` lines carry no package/process name, so zLog can't show
one. Android Studio shows it by resolving each **PID → process name** from the
device separately. Users want the same column.

## Fix

Resolve PID → process name and paint it as an **optional** column (View-menu
toggle, persisted). Full package name shown.

Two complementary, cheap sources feed a per-model `pid -> name` map:

1. **`Start proc` lines** already flowing through the log (parsed by
   `core/proc.parse_proc_start` for the package filter) — merged on every append,
   so it works on live streams and opened files with zero adb calls.
2. **A one-shot `adb shell ps` snapshot** (`core/processes.parse_ps` +
   `adb/processes.list_process_map`) taken when the column is enabled and when a
   stream starts — names the already-running processes (systemui, etc.) that never
   logged a start during capture.

| File | Layer | Change |
|---|---|---|
| `core/processes.py` (new) | core | `parse_ps(output) -> {pid: name}`, tolerant of `-o PID,NAME` and default `ps` layouts. Pure. |
| `adb/processes.py` (new) | adb | `list_process_map(serial, adb_path)` runs `adb shell ps` and returns `parse_ps(...)`. |
| `ui/log_model.py` | ui | `PROCESS_ROLE`; per-model `_pid_names`; merge `Start proc` names in `append_entries`; `merge_process_names()`; `process_col_chars()` (dynamic width, capped 40); clear resets it. |
| `ui/log_delegate.py` | ui | `show_process` flag; paint the name after the tag (width from the source model, right-elided past the cap). |
| `ui/main_window.py` | ui | View-menu "Show &Process Names" (checkable); wire to the delegate + repaint; snapshot on enable/stream-start; `show_process` setting. |
| `core/settings.py` | core | `show_process: False` default. |
| tests | | `parse_ps` shapes; model role + merge + width; toggle persists and flips the delegate. |

## Architecture

- `core/` stays Qt-free (`parse_ps` pure, unit-tested). Worker/adb call isolated in
  `adb/`. Model stays virtualized: names are a dict lookup in `data()`, repaint via a
  single `dataChanged` over the column.
- PID recycling: the map is best-effort; a recycled PID may briefly mislabel or blank
  an old line (same limitation as Android Studio). Documented, acceptable.

## Verification

- [ ] `uv run pytest`
- [ ] ruff clean
- [ ] Manual: enable Show Process Names → column appears with full package names;
  toggle persists across relaunch.
