# Plan: Fix empty device list right after connecting a phone

- **Status:** Done  <!-- Draft | Approved | In progress | Done | Abandoned -->
- **Owner:** unassigned
- **Created:** 2026-07-29
- **Related:** [device-picker.md](device-picker.md), [remember-device.md](remember-device.md)

## Goal

Clicking **Refresh** right after plugging in / authorizing a phone reliably shows
it, instead of sometimes showing an empty picker.

## Why

`adb devices` has a well-known race: if the daemon needed to (re)start, or the
phone finished USB enumeration/authorization only moments before the call, the
very first `adb devices` invocation can return before the server has caught up,
yielding zero rows. `zlog.adb.devices.list_devices()` calls `adb devices` exactly
once and returns whatever it got, so that transient empty result reaches the UI
as-is — `_populate_devices([])` (device count 0, "This PC" still present) reports
"0 device(s) found." and the phone is simply missing until the user clicks
Refresh again. This is a real, previously-reported bug, not a one-off.

## Scope

- **In:** `list_devices()` retries once, after a short delay, specifically when
  the first attempt finds no devices at all — the exact shape of the race.
- **Out (non-goals):** retrying when devices *are* found but in an unexpected
  state (e.g. still `unauthorized` — that's accurate, not a race); changing the
  `adb devices` polling/refresh UX (still manual, no auto-polling); Wi-Fi connect
  (`adb connect`) — same underlying race is conceivable there too, but no report
  of it and it's a separate call, out of scope here.

## Design

| File | Layer | Change |
|---|---|---|
| `src/zlog/adb/devices.py` | adb | `list_devices()`: if the first `parse_devices(proc.stdout)` comes back empty, sleep briefly (~300ms) and issue one more `adb devices` call, returning its result instead. Only ever one retry — a second empty result is treated as genuinely "no devices" and returned as-is. |
| `tests/test_devices.py` or a new `tests/test_adb_devices.py` | tests | Monkeypatch `subprocess.run` to return empty-then-populated output across two calls; assert `list_devices()` returns the populated result and made exactly two calls. A single always-empty run still returns `[]` after exactly two calls (no infinite retry). |

## Architecture touch points

- **Threading:** none — `refresh_devices()` already runs `list_devices()`
  synchronously on the main thread (a short one-shot call, per `adb/devices.py`'s
  own docstring); adding one bounded, short sleep-and-retry keeps that contract
  and just costs an extra ~300ms only in the already-empty case.
- **Dependency direction:** unaffected — the retry stays inside `adb/devices.py`;
  `core/devices.py`'s pure `parse_devices` is untouched.

## Risks & regressions to check

- A genuinely device-less Refresh (nothing plugged in) now takes one extra
  ~300ms round-trip before showing "No devices" — acceptable for a manual,
  infrequent action.
- Must not retry when real devices *are* returned (even if `unauthorized` or
  `offline`) — only an empty list triggers it.
- `list_devices()`'s existing `timeout` parameter still applies per-call, so a
  hanging `adb` still raises `TimeoutExpired` (via `_run_adb`) rather than
  doubling the hang silently.

## Verification

- [x] `uv run pytest` — new `tests/test_adb_devices.py` (3 cases: no-retry-needed,
      retries-once-and-succeeds, genuinely-empty-stays-empty) + full suite, 690 passed
- [x] `uv run ruff check .` and `uv run ruff format --check .`
- [ ] Manual, if a device is available: unplug/replug, click Refresh once instead
      of twice — not verified in this environment (no physical device attached);
      the retry logic itself is fully covered by the mocked-subprocess tests above

## Open questions

None.
