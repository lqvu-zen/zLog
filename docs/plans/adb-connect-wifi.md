# Plan: adb over Wi-Fi / connect by IP

- **Status:** Done
- **Owner:** unassigned
- **Created:** 2026-07-15
- **Related:** [device-picker.md](device-picker.md), backlog.md

## Goal

A "Connect…" button in the device bar runs `adb connect host:port`, then refreshes
the device list — no need to drop to a terminal to pair a wireless device/emulator.

## Scope

- **In:** one button + a small input for `host:port` (port optional, defaults to
  the adb standard `5555`); runs the connect, reports success/failure in the
  status bar, and refreshes the device picker on success.
- **Out (non-goals):** Android 11+ wireless-debugging QR/pairing flow (`adb pair`);
  disconnect UI (users can just stop using the device; `adb disconnect` is a
  possible follow-up); remembering/persisting past connections.

## Design

| File | Layer | Change |
|---|---|---|
| `src/zlog/adb/connect.py` (new) | adb | `connect(host_port: str, adb_path: str = "adb", timeout: float = 5.0) -> str` — runs `adb connect <host_port>` (defaulting to `:5555` if no port given), returns adb's own stdout message. Raises `FileNotFoundError`/`subprocess.TimeoutExpired` like the existing one-shot wrappers (`adb/devices.py`, `adb/packages.py`) so `_run_adb` can catch them the same way. |
| `src/zlog/core/devices.py` | core | `is_connect_ok(message: str) -> bool` — pure parse of adb's reply (`"connected to ..."` / `"already connected to ..."` = success; anything else, e.g. `"failed to connect ..."` / `"cannot connect ..."`, = failure). Unit-tested against real adb wording samples. |
| `src/zlog/ui/main_window.py` | ui | Device-bar `connect_btn` ("Connect…") next to `refresh_btn`; click → `QInputDialog.getText` for `host:port` → `_run_adb(lambda: connect(text, self._adb_path()), ...)` → on a truthy result, show the message and call `refresh_devices()` if `is_connect_ok` is True, else just show the failure message. |

## Architecture touch points

- One-shot subprocess call on the main thread (same pattern as `list_devices` /
  `clear_logcat` — not a stream, so no `QThread` needed).
- `core/devices.py` stays Qt-free; `adb/connect.py` is the only place touching
  `subprocess` for this feature.

## Risks & regressions to check

- Malformed input (empty string, no host) — validate before calling adb, show a
  status message rather than a bad subprocess invocation.
- adb itself missing — routed through the existing `_run_adb` "adb not found" path.
- A successful connect that still shows the device as `unauthorized` (device screen
  needs confirming) — `refresh_devices()` already renders that state via `Device.label`.

## Verification

- [x] `uv run pytest` (`is_connect_ok` cases for adb's known reply strings;
      `connect()` argv via a monkeypatched `subprocess.run`)
- [x] `uv run ruff check .` and `uv run ruff format --check .`
- [x] Headless smoke: Connect… button renders next to Refresh, no crash
      (reasoning-only for the live-connect path — no Wi-Fi-debug device available)

## Open questions

- None blocking; `adb pair` (Android 11+ pairing code flow) is a larger, separate
  feature if wanted later.
