# Plan: Prefer a newly-connected device on Refresh

- **Status:** Done  <!-- Draft | Approved | In progress | Done | Abandoned -->
- **Owner:** unassigned
- **Created:** 2026-07-30
- **Related:** [remember-device.md](remember-device.md), [device-picker.md](device-picker.md), [device-list-refresh-race.md](device-list-refresh-race.md)

## Goal

Plug in a phone and click **Refresh**: the picker selects that phone, instead of
staying on whatever device was previously remembered/selected.

## Why

`choose_device_index` (via `DeviceController.choose_index`) always prefers the
remembered `preferred_serial` when present, regardless of what's new in this
refresh. That's the right default for "reopen zLog, reselect what I had" (see
remember-device.md) but the wrong one for "I just plugged in a different device
and clicked Refresh" — you have to manually reselect it from the dropdown.

## Scope

- **In:** on a Refresh (not the very first population — that's app startup,
  where "remember my last device" must keep working exactly as today), a real
  device whose serial wasn't present in the *previous* refresh wins over the
  remembered one. Multiple new devices at once: the last one in adb's own list
  order wins (trusted as connection order — adb gives no timestamp).
- **Out (non-goals):** persisting "recently connected" across zLog restarts
  (resets each session — first refresh after launch has no baseline, so nothing
  is "new" yet, preserving remember-device.md); reordering the dropdown itself;
  changing auto-reconnect (separate code path, untouched).

## Design

| File | Layer | Change |
|---|---|---|
| `src/zlog/core/devices.py` | core | `choose_device_index(devices, preferred_serial, *, newly_connected=None)` — new keyword-only param, a set of serials. The **last** streamable, non-local device whose serial is in `newly_connected` wins, ahead of `preferred_serial`; empty/`None` (the default) leaves existing behavior byte-for-byte unchanged. Pure, unit-tested. |
| `src/zlog/ui/device_controller.py` | ui | `DeviceController` gains `_known_real_serials: set[str] \| None = None` (starts `None`) and computes `self._newly_connected` inside `set_devices()`: `None` baseline → empty (first-ever call, i.e. app startup); otherwise `current_streamable_real_serials - _known_real_serials`. Tracking *streamable* serials specifically (not just "seen this serial before") means a device that was `unauthorized` on the previous refresh and just got allowed still counts as newly connected once it's usable. `choose_index()` passes the set through to `choose_device_index`. |
| `tests/test_devices.py` | tests | `choose_device_index` cases: a newly-connected serial beats `preferred_serial`; the last of several newly-connected wins; a newly-connected *local* ("This PC") or non-streamable serial is ignored; `newly_connected=None`/omitted matches current behavior exactly. |
| `tests/test_device_controller.py` | tests | First-ever `set_devices()` call still honors `preferred_serial` (no false "new"); a second call adding a serial makes that one win even with a `preferred_serial` set; a second call with an unchanged device list still honors `preferred_serial`. |

## Architecture touch points

- **Threading:** none — `refresh_devices()` is already synchronous on the main
  thread.
- **Dependency direction:** unaffected; `newly_connected` is plain data computed
  in `ui` (`DeviceController`) and consumed by the pure `core` function.

## Risks & regressions to check

- Must not fire on the **first** refresh (app startup) — that would silently
  break remember-device.md by always jumping to "whatever's last in the list"
  on every launch. This is why `_known_real_serials` starts at `None`, not `{}`.
- A device that *drops and reconnects* between two refreshes looks "new" again
  (its serial briefly left `devices`, so it's absent from `_known_real_serials`
  at the next refresh) — acceptable: you likely refreshed because you noticed it
  reconnect, and want it selected.
- "This PC" must never be treated as newly-connected (it's not a real device);
  `choose_device_index` only considers non-local, streamable devices for both
  the "new" check and the win.

## Verification

- [x] Targeted tests: `tests/test_devices.py` + `tests/test_device_controller.py`
      (33 passed) and the broader `-k device` slice across the suite (49 passed)
- [x] `uv run ruff check .` and `uv run ruff format --check .`

## Open questions

None — resolved with the user: override only on new-device-appears (not every
Refresh), and trust adb's own list order for "latest" rather than tracking our
own recency beyond simple first-seen bookkeeping.
