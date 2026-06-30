# Plan: Device picker

- **Status:** Done  <!-- Draft | Approved | In progress | Done | Abandoned -->
- **Owner:** Vũ
- **Created:** 2026-06-30
- **Related:** `package-filter.md` (future — depends on knowing the selected device)

## Goal

Let the user choose which connected device/emulator to stream from, instead of
zLog implicitly using the single default device (and failing when more than one is
attached).

## Scope

- **In:**
  - List attached devices via `adb devices` and show them in a toolbar dropdown.
  - A **Refresh** button to re-scan; auto-scan once at startup.
  - Stream from the selected device: `adb -s <serial> logcat -v threadtime`.
  - Sensible states: no devices → Start disabled with a hint; `offline` /
    `unauthorized` devices shown but not streamable; device combo locked while
    streaming (switching device requires Stop → pick → Start).
- **Out (non-goals, future plans):**
  - Persisting the last-selected device across launches (needs a settings file).
  - Live hot-plug detection (`adb track-devices`); v1 uses manual Refresh.
  - Showing a friendly model name (`getprop`) — v1 shows `serial (state)`.

## Design

| File | Layer | Change |
|---|---|---|
| `src/zlog/core/devices.py` (new) | core | `Device` dataclass (`serial`, `state`) + `parse_devices(output: str) -> list[Device]`. Pure, no Qt/subprocess — just parses `adb devices` text. |
| `src/zlog/adb/devices.py` (new) | adb | `list_devices(adb_path="adb", timeout=5) -> list[Device]`: runs `adb devices`, returns `parse_devices(output)`. Handles `FileNotFoundError`/timeout by raising a clear error or returning `[]`. |
| `src/zlog/adb/reader.py` | adb | `AdbReader(serial: str | None = None, adb_path="adb")`; when `serial` is set, build `[adb, "-s", serial, "logcat", "-v", "threadtime"]`. `serial=None` keeps current default-device behavior. |
| `src/zlog/ui/main_window.py` | ui | Add a device `QComboBox` + **Refresh** `QPushButton` to the toolbar (left of Min level). Populate from `list_devices()` at startup and on Refresh. On Start, pass the selected serial to `AdbReader`. Enable/disable rules below. |
| `src/zlog/__init__.py`, `pyproject.toml` | — | Bump `__version__` / `version` `0.1.0 → 0.2.0` (notable new capability). |
| `tests/test_devices.py` (new) | tests | Cover `parse_devices`: normal multi-device, header-only/empty, `offline`, `unauthorized`, trailing blank lines, the `* daemon started *` noise lines. |
| `.claude/skills/run-zlog/scripts/driver.py` | (skill) | Add a `devices` scenario that injects a fake device list into the combo to screenshot the populated picker (no real adb). |

### UI behavior

- **Enablement:** Start is enabled only when a *streamable* device (`state ==
  "device"`) is selected. While streaming, the device combo and Refresh are
  disabled; Stop re-enables them.
- **Empty:** no devices → combo shows "No devices" (disabled), Start disabled,
  status bar hint: "Connect a device and press Refresh (USB debugging on)."
- **Non-streamable entries:** `offline` / `unauthorized` devices appear as
  `serial (unauthorized)` and are not selectable for Start (or selecting them keeps
  Start disabled with a hint).

## Architecture touch points

- **Threading:** `adb devices` is a short, one-shot subprocess — *not* a stream.
  v1 calls `list_devices()` **synchronously on the main thread** (on startup and on
  Refresh) with a timeout. This does not violate the worker-thread rule: it returns
  data to the caller; it never touches widgets from another thread. The only
  long-running work (the logcat stream) stays in `AdbReader` (a `QThread`) reaching
  the UI via signals, exactly as today.
  - *Risk & fallback:* the very first `adb` call can briefly block while the adb
    server starts. Mitigated by the timeout. If it feels janky in practice, a
    follow-up plan moves device listing into a small `QThread` that emits a
    `devices_ready` signal — noted as a non-goal here to keep v1 small.
- **Model/proxy:** unchanged. No new columns or filter predicates.
- **Dependency direction:** `core/devices` (pure) ← `adb/devices` ← `ui`;
  `AdbReader` gains a `serial` param. All arrows stay one-way (`ui → adb → core`).
- **Colors/theme:** none.

## Risks & regressions to check

- Start/Stop/Clear still work; autoscroll-at-bottom unaffected.
- Single device, no selection made → still streams (default selection = first
  streamable device).
- Multiple devices → always passes `-s`, fixing the old "more than one
  device/emulator" failure.
- Device combo correctly locks during streaming and unlocks on Stop.
- Selected device disconnects mid-stream → the logcat process ends; existing
  `error`/stop handling covers it (verify no crash).
- `adb` missing → `list_devices` surfaces the same clear message as the reader.

## Verification

- [x] `uv run pytest` (new `test_devices.py` green)
- [x] `uv run ruff check .` and `uv run ruff format --check .`
- [x] `run-zlog` `devices` scenario screenshot shows the populated picker; `smoke`
      still renders
- [ ] Manual (if a device is available): pick a device, Start, see its logs; Stop,
      switch, Start again
- [ ] Manual: with no device connected, Start is disabled and the hint shows

## Open questions

- Default selection when multiple streamable devices exist: first in list, or none
  (force an explicit pick)? Proposed: **first streamable device**.
- For `unauthorized`/`offline`: list-but-disable (proposed) vs hide entirely?
- Confirm the `0.2.0` version bump is the right granularity for this feature.
