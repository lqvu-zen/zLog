# Plan: Clear on Start option

- **Status:** Done  <!-- Draft | Approved | In progress | Done | Abandoned -->
- **Owner:** Vũ
- **Created:** 2026-07-01
- **Related:** persists via `settings-persistence.md`

## Goal

Let the user opt into automatically clearing the previous log when starting a new
stream, so each capture begins fresh — without pressing Clear every time.

## Scope

- **In:** a checkable **View → Clear on Start** option (default off). When on, Start
  clears the model before streaming. The choice is remembered across launches.
- **Out:** clearing on device change, or an auto-clear timer.

## Design

| File | Layer | Change |
|---|---|---|
| `src/zlog/core/settings.py` | core | add `"clear_on_start": False` to `DEFAULTS`. |
| `src/zlog/ui/main_window.py` | ui | add a checkable **Clear on Start** action to the View menu; in `start()`, if it's checked, call `self.model.clear()` before creating the reader. Load/save it in the settings methods. |

## Architecture touch points

- **Model/threading:** reuses the existing virtualized `model.clear()`; no new
  threading. The clear happens on the main thread before the reader starts.
- **Dependency direction:** UI-only + one pure `DEFAULTS` key. `core` stays Qt-free.
- **Versioning:** no bump (next bump is at the 1.1 release).

## Risks & regressions to check

- With the option on, Start empties the previous log; with it off, Start appends
  (current behavior).
- The setting persists and restores.
- Nothing else regresses (counts reset with the clear; placeholder updates).

## Verification

- [x] `uv run pytest`
- [x] `uv run ruff check .` and `uv run ruff format --check .`
- [x] Headless: seed rows, enable the option, call `start()` → model is emptied
- [ ] Manual: toggle it, stream twice, confirm the second stream starts clean
