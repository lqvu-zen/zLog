# Plan: Watch-pattern notifications

- **Status:** Done
- **Owner:** unassigned
- **Created:** 2026-07-11
- **Related:** ROADMAP v2.0 (watch-pattern desktop notifications), [exclude-filter.md](exclude-filter.md)

## Goal

After this ships, you can set a **watch pattern**; when a newly-captured line
matches it, zLog raises a desktop notification (tray balloon, or a status-bar
flash + beep if no tray) — so you can look away and be pinged when the event you
care about happens.

## Scope

- **In:** a substring watch matcher (case-insensitive), checked against incoming
  batches; throttled notification via `QSystemTrayIcon` with a status/beep
  fallback; set via a View dialog; persisted.
- **Out:** regex watches (substring is enough to start), multiple watches,
  per-watch sounds, notification history.

## Design

| File | Layer | Change |
|---|---|---|
| `src/zlog/core/settings.py` | core | Add `"watch": ""`. |
| `src/zlog/ui/main_window.py` | ui | State `_watch` (matcher or None), `_watch_pattern`, `_watch_last` (throttle), `_tray`. `_apply_watch(pattern, announce)` compiles the matcher via `compile_matcher(...)`. `_watch_hits(entries)` returns matching entries. In `on_batch` (after autosave, before the pause gate), notify on the last hit. `_notify_watch(entry)` throttles to once/3s and shows a tray balloon (`_ensure_tray`) or falls back to status + `QApplication.beep()`. View → **Set &Watch…** (QInputDialog). Settings spec `("watch", getter, setter→_apply_watch(announce=False))`. |
| `tests/test_main_window_settings.py` | tests | `_watch_hits` finds matching lines; clearing the pattern disables it. |

## Architecture touch points

- **Pure-ish match:** `_watch_hits` is testable without a display; only delivery
  touches Qt/tray.
- **Captures all lines:** the watch runs before the Pause early-return, so paused
  captures still notify.
- **Declarative settings parity** preserved.

## Risks & regressions to check

- **No system tray:** guard with `QSystemTrayIcon.isSystemTrayAvailable()`; fall
  back to status + beep so headless/test never crashes.
- **Notification spam:** throttle to once every 3 s.
- **Empty pattern:** clears the watch (matcher None), no checks.

## Verification

- [ ] `uv run pytest`
- [ ] `uv run ruff check .` and `uv run ruff format --check .`
- [ ] Manual: set a watch, stream a matching line, get a notification.
