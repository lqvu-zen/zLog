# Plan: Stream Windows debug output from the device box ("This PC")

- **Status:** Done  <!-- Draft | Approved | In progress | Done | Abandoned -->
- **Owner:** unassigned
- **Created:** 2026-07-24
- **Related:** [windows-debug-output.md](windows-debug-output.md), [device-picker.md](device-picker.md), [windows-app-focus.md](windows-app-focus.md), [windows-event-log.md](windows-event-log.md)

## Goal

Capture Windows debug output the same way you capture from a phone: pick
**This PC** in the device dropdown and press **Start**. One streaming flow for
every source, instead of a separate File-menu command that behaves differently.

## Why

Today the device box + Start is the mental model for "get logs", but the Windows
capture hides behind **File → Capture Windows Debug Output** — a second, unrelated
gesture for the same job. Folding it into the picker means Start/Stop/Pause,
Clear-on-Start, the tab label, and auto-selection all work identically whatever
you're capturing. It also gives the later
[Event Log](windows-event-log.md) and [file-follow](file-follow.md) sources an
obvious home: more entries in the same list.

## Scope

- **In:** a pseudo-device entry ("This PC (debug output)") in the device picker on
  Windows; `Start` routes it to `DebugOutputReader`; Stop/Pause/Clear and the tab
  label behave as for a device. The existing File-menu item keeps working as a
  shortcut.
- **Out (non-goals):** listing Event Log channels or followed files as entries
  (their own plans), a redesigned picker widget, and showing the entry on
  non-Windows platforms.

## Design

The picker already stores a **serial string** as each item's `data`, and
`start()` reads `device_box.currentData()`. So a reserved sentinel serial flows
through the existing machinery untouched — no new widget, no parallel state.

`_populate_devices` prepends the local entry; `start()` branches on the sentinel
and calls the capture path that already exists (`capture_debug_output`), so the
reader wiring, tab labelling, and teardown are unchanged and already tested.

| File | Layer | Change |
|---|---|---|
| `src/zlog/core/devices.py` | core | `LOCAL_DBWIN = "local:dbwin"` sentinel; `is_local_source(serial) -> bool` (any `local:` prefix, so future local sources join in); `local_device()` returning `Device(LOCAL_DBWIN, "device")` with a friendly `label`. Give `Device.label` a special case so it renders "This PC (debug output)" rather than the raw serial. All pure, unit-tested. |
| `src/zlog/ui/main_window.py` | ui | `_populate_devices`: on Windows prepend `local_device()` **before** the adb list, and drop the "No devices" early-return when the local entry exists (otherwise the box is disabled on a machine with no phone attached — the main use case). `start()`: if `is_local_source(serial)` → `capture_debug_output()` and return; else the current adb path. `_update_start_enabled` needs no change (the entry carries data, so Start enables). Disable the adb-only controls (package box/Load/Apply, Clear device, dumpsys, Wi-Fi) while a local source is selected. Guard auto-reconnect (`_try_reconnect`, `want_stream`) so a local capture never polls `adb devices` to "come back". |
| `src/zlog/ui/menus.py` | ui | Keep **Capture Windows Debug Output** as a shortcut to the same method (one code path); retitle it "…(This PC)" so it reads as the same thing. |
| `docs/GUIDE.md` | — | Rewrite the Windows section around: pick **This PC** → **Start**. Mention the menu item as an alias. |
| `tests/test_devices.py`, `tests/test_main_window_dbwin.py` | — | Pure: sentinel detection, label, `choose_device_index` with the local entry present. Window: the entry appears on Windows only; selecting it and pressing Start routes to the DBWIN path (monkeypatched reader) rather than `AdbReader`; adb-only buttons disable; the picker isn't disabled when no phone is attached. |

## Architecture touch points

- **Threading:** none new — `capture_debug_output` already attaches through
  `CaptureController`.
- **Model/proxy:** none.
- **Dependency direction:** the sentinel and its predicate are Qt-free in
  `core/devices.py`, where the rest of the device vocabulary lives.

## Risks & regressions to check

- **The "No devices" path** is the subtle one: today an empty adb list disables
  the picker and tells you to connect a phone. With a local entry that must not
  happen — otherwise the feature is unreachable on a machine with no device.
- **Remembered serial:** `preferred_serial` could now persist `local:dbwin` and
  reselect it next launch. Decide deliberately (see open questions) and make sure
  a remembered *device* still wins when it's back.
- **Auto-reconnect must not fire** for a local source — `is_serial_streamable`
  answers about adb devices, so a local sentinel would look "gone" and trigger
  endless reconnect attempts.
- **adb-only actions** (package filter, Clear device buffer, dumpsys, Wi-Fi,
  merged view) are meaningless for This PC — disable rather than fail at runtime.
- **Non-Windows:** the entry must not appear at all (not appear-and-error).
- **Existing tests** assert `capture_debug_output` behaviour and device-box
  contents; both change shape — update deliberately, don't just make them pass.
- `start_merged` iterates `devctl.devices` — it must skip the local entry.

## Verification

- [ ] `uv run pytest` (routing, picker contents, disabled adb controls, no-phone case)
- [ ] `uv run ruff check .` and `uv run ruff format --check .`
- [ ] `run-zlog` screenshot of the picker showing **This PC** alongside a device
- [ ] Manual on Windows: with **no** phone attached, pick This PC → Start →
      debug lines arrive; Stop; then attach a phone and confirm both entries list
      and streaming still works for the device.

## Open questions

- **Remember This PC as the last-used source?** Convenient for Windows-only users,
  surprising if you mostly use a phone. Leaning yes (it's just another serial),
  but only if a real device isn't preferred.
- **Label:** "This PC (debug output)" vs. "Local · OutputDebugString" vs. plain
  "This PC". Leaning "This PC (debug output)" — says what it captures.
- **Position:** first in the list, or after the devices? Leaning first, so it's
  visible when no device is attached.
- Should the File-menu item be **removed** once the picker works, rather than
  kept as an alias? Leaning keep-as-alias for one release, then reassess.
