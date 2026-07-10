# Plan: Surface "Clear device buffer" as a toolbar button

- **Status:** Done
- **Owner:** unassigned
- **Created:** 2026-07-10
- **Related:** [clear-device-buffer.md](clear-device-buffer.md) (added the action +
  `adb logcat -c` plumbing), [two-bar-header.md](two-bar-header.md)

## Goal

After this ships, the device bar has a clearly-labeled button that wipes the
**device's** logcat ring buffer (`adb logcat -c`), distinct from the ✕ button that
only clears the in-app view. No more hunting in the View menu.

## Why

The ✕ "Clear" button calls `model.clear()` — it empties what zLog is showing, not
the device. Clearing the device buffer already exists (`_clear_device_buffer` →
`clear_logcat`) but only as a View-menu item, so users reasonably think there's no
way to do it. This is purely surfacing existing, tested logic.

## Scope

- **In:** a `Clear device` button on the device bar wired to the existing
  `_clear_device_buffer`; disambiguate the ✕ tooltip to "Clear the log view".
- **Out:** confirmation dialog (the View action has none; keep parity), any change
  to the `adb logcat -c` plumbing, removing the existing menu item (keep both).

## Design

| File | Layer | Change |
|---|---|---|
| `src/zlog/ui/main_window.py` | ui | Add `self.clear_device_btn = QPushButton("Clear device")` in `_build_widgets` with tooltip "Wipe the device's logcat buffer (adb logcat -c)". Place it on `device_row` right after the ✕ `clear_btn`. Connect `clicked → self._clear_device_buffer` in `_connect_signals`. Change the ✕ tooltip from "Clear the log" to "Clear the log view". Keep the `Clear device log &buffer` menu item. |
| `tests/test_main_window_settings.py` | tests | `clear_device_btn` exists and, clicked with no device selected, routes to `_clear_device_buffer` (status message mentions "device"), i.e. it doesn't crash and reuses the guarded path. |

## Architecture touch points

- **Threading:** none new — `_clear_device_buffer` runs the one-shot `adb logcat -c`
  through the existing `_run_adb` guard on the main thread (short, not a stream).
- **Model/proxy:** untouched — this does not clear the in-app view.
- **Dependency direction:** unchanged.

## Risks & regressions to check

- **Don't confuse the two clears.** The ✕ (view) and `Clear device` (buffer) must
  read as different actions — hence the tooltip split and the explicit label.
- **No device selected:** button must degrade to the existing "Select a device
  first." status message, not error.
- **Layout:** the extra button shouldn't crowd the device bar — it sits in the
  stream-controls group before Follow; there's a stretch after, so spacing holds.

## Verification

- [ ] `uv run pytest`
- [ ] `uv run ruff check .` and `uv run ruff format --check .`
- [ ] New test covers the no-device path via the button.
- [ ] Screenshot the device bar showing both ✕ and "Clear device".
