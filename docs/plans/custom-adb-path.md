# Plan: Custom adb path

- **Status:** Done
- **Owner:** unassigned
- **Created:** 2026-07-15
- **Related:** [settings-dialog.md](settings-dialog.md), [settings-persistence.md](settings-persistence.md), backlog.md

## Goal

A **Capture** tab field in Settings lets the user point zLog at a specific `adb`
executable, for when it isn't on `PATH` — every adb-backed call (device list,
streaming, connect, clear buffer, package/PID resolution) uses it.

## Scope

- **In:** one settings key + a text field (with a "Browse…" file picker) in
  `SettingsDialog`'s Capture tab; every existing call site that currently hardcodes
  the `adb_path="adb"` default reads the setting instead.
- **Out (non-goals):** validating the path points at a real/working adb binary up
  front (existing `_run_adb` "not found" handling already surfaces a bad path
  clearly on first use); auto-discovering platform-tools installs.

## Design

| File | Layer | Change |
|---|---|---|
| `src/zlog/core/settings.py` | core | `DEFAULTS["adb_path"] = ""` (empty = use `"adb"` from `PATH`, matching every wrapper's own default). |
| `src/zlog/ui/settings_dialog.py` | ui | Capture tab: a `QLineEdit` + "Browse…" (`QFileDialog.getOpenFileName`) for the adb path, alongside the existing log-buffers/tail-count/max-rows controls. `get_values()` includes it. |
| `src/zlog/ui/main_window.py` | ui | `self._adb_path() -> str` returns `self.settings.get("adb_path") or "adb"`. Replace every hardcoded default at existing call sites — `refresh_devices` (`list_devices`), `_try_reconnect` (`list_devices`), `_start_reader` (`AdbReader(...)`), `_clear_device_buffer` (`clear_logcat`), the package/PID lookups (`list_packages`/`resolve_pids`), and the new `adb-connect-wifi` button — with `self._adb_path()`. Collected/applied in `_collect_settings`/`_apply_settings_values` alongside the other Capture-tab fields. |

## Architecture touch points

- Purely wiring an existing parameter that every adb wrapper (`adb/devices.py`,
  `adb/reader.py`, `adb/packages.py`) already accepts — no new subprocess
  surface, no threading change.
- Settings round-trip follows the exact pattern already used for `log_buffers`/
  `tail_count`/`max_rows` (`settings-dialog.md`).

## Risks & regressions to check

- Every call site that previously relied on the `adb_path="adb"` default must be
  updated — a missed one silently ignores a custom path. Grep `list_devices(`,
  `AdbReader(`, `clear_logcat(`, `list_packages(`, `resolve_pids(` before closing
  this out.
- An empty setting must still resolve to plain `"adb"` (not `""`, which would break
  `subprocess.Popen`/`subprocess.run`).
- Changing the path mid-session doesn't require a restart — the next adb call
  reads the current setting.

## Verification

- [x] `uv run pytest` (`_adb_path()` empty-vs-set behavior; settings round-trip
      includes `adb_path`)
- [x] `uv run ruff check .` and `uv run ruff format --check .`
- [x] Headless smoke: app renders with no regressions (`run-zlog` driver)

## Open questions

- None blocking.
