# Plan: Autosave / rotating capture to disk

- **Status:** Done
- **Owner:** unassigned
- **Created:** 2026-07-11
- **Related:** ROADMAP v1.3 "Sessions & export", [save-load.md](save-load.md),
  [ring-buffer-cap.md](ring-buffer-cap.md)

## Goal

After this ships, an opt-in **View → Autosave Capture** toggle streams incoming
log lines to a file on disk as they arrive, so a crash/close doesn't lose the
capture. The file is size-capped and rolls over to a single `.1` backup to bound
disk use.

## Scope

- **In:** append each incoming batch (as threadtime text) to an autosave file in
  the app-data dir while streaming; rotate to `<name>.1.log` past a byte cap;
  opt-in toggle + `autosave` setting; disable on write error (don't spam).
- **Out:** choosing the autosave path, N-deep rotation (one backup is enough),
  autosaving opened files (only live capture), compressing.

## Design

| File | Layer | Change |
|---|---|---|
| `src/zlog/core/autosave.py` | core | `AUTOSAVE_CAP = 10 MB`; `rotate_path(path)` inserts `.1` before the extension; `should_rotate(size, incoming, cap)` — appending would exceed the cap. Pure (string/arithmetic only). |
| `src/zlog/core/settings.py` | core | Add `"autosave": False`. |
| `src/zlog/ui/main_window.py` | ui | `import os`. A checkable `autosave_action` in the View menu (after Reopen Last). `_autosave_path()` → `<AppDataLocation>/autosave.log`. `_autosave(entries)`: if enabled, rotate when the existing file would exceed `self._autosave_cap` (default `AUTOSAVE_CAP`), then append `entries_to_text(entries)`; on `OSError`, uncheck the toggle + report. Call it in `on_batch` right after timestamp tracking (so it captures even while paused). Settings spec `("autosave", isChecked, setChecked)`. |
| `tests/test_autosave.py`, `tests/test_main_window_settings.py` | tests | `rotate_path`/`should_rotate` behavior; a window test that autosave writes the file and rotates once past a tiny cap. |

## Architecture touch points

- **core stays Qt-free / tested;** the rotation *decision* is pure, the file write
  lives in the UI slot on the main thread (small appends, cheap).
- **Captures all lines:** `_autosave` runs before the Pause early-return, so paused
  captures are still written.

## Risks & regressions to check

- **First write:** don't try to rotate a file that doesn't exist yet (guard on
  size > 0).
- **Write failure:** disable autosave and message once rather than erroring every
  batch.
- **Encoding:** measure the incoming size in UTF-8 bytes, not characters.

## Verification

- [ ] `uv run pytest`
- [ ] `uv run ruff check .` and `uv run ruff format --check .`
- [ ] Manual: enable, stream, confirm the autosave file grows and rolls over.
