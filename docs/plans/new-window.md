# Plan: Multiple concurrent streams via New Window

- **Status:** Done
- **Owner:** unassigned
- **Created:** 2026-07-11
- **Related:** ROADMAP v2.0 (multiple device tabs)

## Goal

After this ships, File → **New Window** opens a second, fully independent zLog
window, so you can stream/inspect two devices at once — delivering concurrent
multi-device viewing without the large tabbed-multi-stream refactor.

## Why this instead of tabs

Each `MainWindow` already owns a complete, independent reader+model+view+filters
stack. Spawning another top-level window reuses all of it as-is (zero refactor,
zero risk to the existing single-window code), and Qt happily runs multiple
top-level windows in one app. Tabs would require hoisting the entire window into a
per-tab widget — a big, risky change better done on its own after a release.

## Design

| File | Layer | Change |
|---|---|---|
| `src/zlog/ui/main_window.py` | ui | Class attr `_open_windows: list` (keeps spawned windows from being garbage-collected). File → **New &Window** (Ctrl+Shift+N) → `_new_window()` creates a `MainWindow`, appends it, and `show()`s it. |
| `tests/test_main_window_settings.py` | tests | `_new_window()` grows `_open_windows` and the new window has its own model (independent stack). |

## Architecture touch points

- **Fully independent instances:** each window has its own `AdbReader`, model, proxy,
  and in-memory filter state; nothing is shared but the on-disk settings file.
- **No new threading model:** each window's reader reaches only its own UI via signals.

## Risks & regressions to check

- **GC:** without a kept reference a spawned window would be collected immediately;
  the class list holds them.
- **Shared settings/autosave file:** both windows read/write the same settings and
  (if enabled) the same autosave path — last write wins; acceptable, note as a
  known limitation (per-window session save is the workaround).

## Verification

- [ ] `uv run pytest`
- [ ] `uv run ruff check .` and `uv run ruff format --check .`
- [ ] Manual: New Window, pick a second device, stream both at once.
