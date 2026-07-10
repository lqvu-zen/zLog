# Plan: "Clear device" should also clear the view

- **Status:** Done
- **Owner:** unassigned
- **Created:** 2026-07-10
- **Related:** [clear-device-button.md](clear-device-button.md),
  [clear-device-buffer.md](clear-device-buffer.md)

## Goal

After this ships, pressing **Clear device** visibly resets zLog: it wipes the
device's logcat buffer *and* empties the in-app view, so the user sees a clean
slate (then fresh lines if streaming) instead of no apparent change.

## Why (bug report)

`adb logcat -c` clears the on-device ring buffer, but it does **not** retroactively
remove lines already pulled into zLog's view, and a running stream isn't affected.
So today the button appears to "do nothing" — it succeeds silently while the view
is unchanged. Users read that as broken. Clearing the view on success makes the
action's effect visible and matches intent: those on-device lines are now gone.

## Scope

- **In:** after a successful `clear_logcat`, call `self.model.clear()` and update
  the status message to say both were cleared.
- **Out:** confirmation dialog; changing the plain ✕ (view-only) button; touching
  the `adb logcat -c` plumbing or the reader stream.

## Design

| File | Layer | Change |
|---|---|---|
| `src/zlog/ui/main_window.py` | ui | In `_clear_device_buffer`, on `ok` also `self.model.clear()`; message → `Cleared the device log buffer and view ({serial}).` |
| `tests/test_main_window_settings.py` | tests | With `clear_logcat` stubbed to succeed and a serial forced, clicking `clear_device_btn` empties the model. The existing no-device test still holds. |

## Architecture touch points

- **Model virtualized:** `model.clear()` already uses `beginResetModel` — correct
  path, no new plumbing.
- **Threading:** unchanged — `clear_logcat` is the existing one-shot on the main
  thread via `_run_adb`.

## Risks & regressions to check

- **Only clear the view on success:** if `adb logcat -c` fails, keep the view
  (the error message shows). The `model.clear()` sits inside the `if ok:` branch.
- **Streaming:** after clearing, a live stream immediately refills with new lines —
  expected and desirable (proves it's live), not a regression.

## Verification

- [ ] `uv run pytest`
- [ ] `uv run ruff check .` and `uv run ruff format --check .`
- [ ] New test: successful clear empties the model; failure leaves it.
