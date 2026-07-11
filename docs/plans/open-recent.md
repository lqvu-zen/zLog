# Plan: Open Recent menu

- **Status:** Done
- **Owner:** unassigned
- **Created:** 2026-07-11
- **Related:** ROADMAP v1.3 "Sessions & export", [save-load.md](save-load.md),
  [search-history.md](search-history.md) (reuses the same history helpers)

## Goal

After this ships, File → **Open Recent** lists the recently opened/saved `.log`
files (most-recent-first, de-duplicated, capped), so returning to a capture is one
click. The list persists across launches.

## Scope

- **In:** track recent log paths (on Open and on Save); a File → Open Recent
  submenu with a Clear Recent entry; persist as a `recent_files` setting; drop a
  path from the list if it's gone when clicked.
- **Out:** auto-reopening the last session on launch (separate item), session
  bundles, tracking exported CSV/JSON/HTML (not reopenable by zLog).

## Design

| File | Layer | Change |
|---|---|---|
| `src/zlog/core/settings.py` | core | Add `"recent_files": []` to DEFAULTS. |
| `src/zlog/ui/main_window.py` | ui | State `self._recent: list[str]`. Factor `open_log`'s read+load into `_load_log_file(path)`. Add a File → **Open Recent** submenu built by `_rebuild_recent_menu()` (basename label, full-path tooltip, `_load_log_file` on click; a Clear Recent action; a disabled "(none)" when empty). `_remember_recent`/`_forget_recent`/`_clear_recent` use `push_history`/`normalize_history` (limit 10) and persist. Call `_remember_recent` on successful open and on `_write_log` save; `_forget_recent` when a recent file fails to open. Settings spec `("recent_files", getter, setter)` restores + rebuilds the menu. |
| `tests/test_main_window_settings.py` | tests | Opening a temp `.log` adds it to `_recent` (front, de-duplicated); opening a missing recent removes it. |

## Architecture touch points

- **Reuses `core/history.py`** (pure, tested) for the MRU/dedup/cap logic — no new
  algorithm.
- **Persistence** rides the existing declarative settings table.

## Risks & regressions to check

- **Stale entries:** a deleted/moved file must be dropped (and the menu rebuilt)
  rather than erroring repeatedly.
- **Menu rebuild timing:** `_recent` is initialized before `_build_menus`; the
  settings restore rebuilds it after load.

## Verification

- [ ] `uv run pytest`
- [ ] `uv run ruff check .` and `uv run ruff format --check .`
- [ ] Manual: open a couple of logs, see them under Open Recent, reopen one.
