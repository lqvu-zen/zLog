# Plan: Settings persistence

- **Status:** Done  <!-- Draft | Approved | In progress | Done | Abandoned -->
- **Owner:** Vũ
- **Created:** 2026-07-01
- **Related:** resolves the "persist across launches" non-goals in `theming-dark-mode.md`,
  `pause-autoscroll.md`, and `tag-highlight.md`

## Goal

Remember the user's preferences between runs, so zLog opens the way they left it —
same theme, window size, filters, follow toggle, and tag highlights.

## Scope

- **In:** persist and restore on launch:
  - **theme** (Light/Dark)
  - **window geometry** (size + position)
  - **Follow** toggle, **Min level**, **Regex** toggle
  - **tag highlights** (tag → color)
  - Stored as a small JSON file in the OS config dir; save on close, load on start.
- **Out (non-goals):** persisting the last device/package filter (device-specific,
  can go stale); syncing settings; a settings UI (it's implicit — the app remembers).

## Design

Serialization is pure and testable in `core`; only the file *location* (OS config
dir) and applying values to widgets are Qt/UI concerns.

| File | Layer | Change |
|---|---|---|
| `src/zlog/core/settings.py` (new) | core | `DEFAULTS` dict; `load_settings(path) -> dict` (merges over defaults; tolerant of a missing or corrupt file → defaults; ignores unknown keys); `save_settings(path, data)`. Pure JSON, no Qt. |
| `src/zlog/core/__init__.py` | core | export `DEFAULTS`, `load_settings`, `save_settings`. |
| `src/zlog/app.py` | ui | set `QApplication.setApplicationName("zlog")` so `QStandardPaths` resolves a proper per-user config dir. |
| `src/zlog/ui/log_model.py` | ui | add `tag_colors() -> dict[str, str]` (current highlights as hex) so they can be saved. |
| `src/zlog/ui/main_window.py` | ui | `_settings_path()` via `QStandardPaths.AppConfigLocation`; `_load_and_apply_settings()` at the end of `__init__` (restores geometry via `restoreGeometry`, sets theme/follow/level/regex, re-applies tag highlights); `_save_settings()` called from `closeEvent`. |
| `tests/test_settings.py` (new) | tests | missing file → defaults; save→load round-trip; corrupt JSON → defaults; unknown keys dropped; `tag_highlights` preserved. |

## Architecture touch points

- **Threading/model:** none. Load/save happen on the main thread at startup/shutdown.
- **Dependency direction:** serialization is pure `core/settings.py`; the UI owns the
  path (`QStandardPaths`) and applying values. `core` stays Qt-free and unit-testable.
- **Geometry** is stored as a base64 string of `saveGeometry()` — an opaque blob the
  UI produces/consumes; `core` just stores the string.
- **Robustness:** a missing/corrupt settings file never breaks startup (falls back to
  defaults). The `run-zlog` driver never triggers `closeEvent`, so it won't write
  settings during headless screenshots.
- **Versioning:** no bump (release-only).

## Risks & regressions to check

- First launch (no file) uses defaults; nothing crashes.
- Corrupt/hand-edited file → defaults, no crash.
- Round-trip: set theme Dark, resize, add a highlight, close, reopen → all restored.
- Restored `min_level`/`regex` actually re-apply to the proxy (not just the widgets).
- Saving creates the config dir if missing; failure to write is non-fatal.

## Verification

- [x] `uv run pytest` (new `test_settings.py` green)
- [x] `uv run ruff check .` and `uv run ruff format --check .`
- [x] `run-zlog` `smoke` still renders (no settings side effects headless)
- [ ] Manual: change theme + size + a tag highlight, close, reopen → state restored

## Open questions

- Persist **window position** too (proposed) or size only (avoids off-screen issues
  on monitor changes — though `restoreGeometry` handles that)?
- Also remember the **search text**? (Could be surprising on reopen — proposed: no.)
