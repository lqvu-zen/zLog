# Plan: Log-driven package selector, two-way synced with the filter

- **Status:** Done
- **Owner:** unassigned
- **Created:** 2026-07-16
- **Related:** [package-filter.md](package-filter.md), [package-bar.md](package-bar.md),
  [quick-filter-pid-package.md](quick-filter-pid-package.md), [live-pid-tracking.md](live-pid-tracking.md)

## Goal

After this ships, the **Package** selector is driven entirely by the current log:
**Load** fills its dropdown with the process/package names the log has parsed (no
`adb`), picking one applies a `proc:` filter through the query bar, and typing a
`proc:` token in the query updates the dropdown — the selection and the filter
stay in sync both ways, and it all works offline on an opened log.

## Scope

- **In:** populate the package dropdown from `LogTableModel`'s known process
  names; selecting/entering a package sets a `proc:<name>` query token; "Clear
  pkg" removes it; the query's `proc:` (and `package:`, now treated the same)
  token mirrors back into the box. Enable the package controls whenever there's
  a log, not only when a device is connected.
- **Out (non-goals):** the adb path for the box — `list_packages` (device's
  installed packages), `resolve_pids` (package→live PIDs), and live-PID tracking
  are **retired from the box** (see Decisions). Filtering by exact PID via the
  `pid:` token is unchanged. `DeviceController`'s package-filter methods stay
  (still unit-tested) but are no longer wired to the box.

## Decisions (confirmed with the user, 2026-07-16)

- **Log-driven only** — the box no longer calls `adb`. Because `proc:` matches by
  process *name*, a restarted app (new PID, same package) is matched
  automatically, so the old live-PID-tracking machinery is unnecessary and is
  unwired.
- **Maps to `proc:`** — the box represents the process-name filter, which works
  on live and offline logs alike.

## Design

| File | Layer | Change |
|---|---|---|
| `src/zlog/ui/log_model.py` | ui | New `process_names() -> list[str]` — sorted, de-duplicated non-empty values of `_pid_names` (the pid→name map already built from "Start proc" lines and `merge_process_names`). |
| `src/zlog/ui/main_window.py` | ui | **`load_packages`**: replace the adb call with `self.package_box`-repopulate from `self.model.process_names()` (block signals while clearing/adding so it doesn't self-trigger; preserve the current edit text). **`apply_package_filter`**: instead of adb PID resolution, `self._add_query_token(f"proc:{name}")` when the box has text, else clear. **`clear_package_filter`**: new `_remove_query_token("proc")` + clear the box text. Connect **`package_box.textActivated`** → `apply_package_filter` so picking an item filters immediately (Enter already does via `returnPressed`). **`_apply_query`**: replace the `spec.package` adb block (currently calls `apply_package_filter`/`clear_package_filter`) with a box↔proc mirror — compute `effective = spec.process or spec.package`, feed it to the existing `self.proxy.set_proc(...)` call, and `self.package_box.setEditText(effective)` (guarded via a `_query_proc` field like the old `_query_package`, to avoid redundant work). Remove `_track_new_pids` and its `on_batch` call (dead once the box stops setting `devctl` PID filters). Drop the now-unused `list_packages, resolve_pids` imports. **`_update_package_enabled`**: enable the package controls always (or when `model.rowCount() > 0`) rather than gating on a device serial. |
| `tests/test_log_model.py` | tests | `process_names()` returns sorted distinct names from `_pid_names` (populated via `merge_process_names` and/or a "Start proc" line), empty when none. |
| `tests/test_main_window_settings.py` (or a small new test) | tests | Two-way sync: setting the box text + `apply_package_filter` puts `proc:<name>` in the query and filters; typing `proc:<name>` into the query mirrors into the box; "Clear pkg" removes the token and empties the box. |

## Architecture touch points

- **Single filter path preserved:** the box drives the filter only through the
  query bar (`proc:` token → `_apply_query` → `proxy.set_proc`), so there's still
  exactly one place filtering is applied and the two-way sync can't diverge.
- **Qt-free-ish model accessor:** `process_names()` is pure list logic over an
  existing dict; no Qt threading, no new state.
- **No worker threads:** the box no longer shells out to `adb`, so the
  `_run_adb`/`QThread` path is untouched here (still used by Connect / Clear
  device / device list).
- **Dependency direction** holds — `ui` only; `core` untouched.

## Risks & regressions to check

- **Offline logs with no "Start proc" lines:** `process_names()` is empty, so
  Load yields an empty dropdown — expected; the user can still type a `proc:`
  value by hand. Confirm no crash on an empty map.
- **Feedback loop:** `apply_package_filter` → `_add_query_token` → `_set_query_text`
  → `_apply_query` → `setEditText(same)` must not re-trigger apply. `setEditText`
  doesn't emit `textActivated`/`returnPressed`, and the repopulate blocks signals,
  so the loop is broken — verify with a test.
- **`package:` token semantics change:** `package:com.x` now filters by process
  name (like `proc:`) instead of adb-resolved PIDs. This is intended under
  "log-driven only"; note it so it's not mistaken for a regression. `pid:` is the
  path for exact-PID filtering.
- **Presets / sessions:** presets store the raw query text (`proc:` token travels
  with it) so they still round-trip; the legacy `package` preset field becomes
  cosmetic. Confirm applying a saved preset with a `proc:` token repopulates the
  box via the mirror.
- **Enable state:** package controls should be usable on an opened log with no
  device; confirm they're enabled and Clear device / streaming still behave.

## Verification

- [x] `uv run pytest` (390 passed; 1 pre-existing unrelated timing flake)
- [x] `uv run ruff check .` and `uv run ruff format --check .`
- [x] Smoke / screenshot via `run-zlog` (new `package-from-log` scenario): Load
      fills the dropdown from the log's process names, picking one sets a
      `proc:com.example.app` token and filters to "Showing 40 of 56 lines" —
      with **no device connected**
- [x] Two-way sync + alias behavior covered by `tests/test_package_selector.py`
      (load-from-log, apply→proc token, query→box mirror, `package:`≡`proc:`,
      clear removes token) and `tests/test_log_model.py::test_process_names_*`
- [x] Docs: `docs/GUIDE.md` updated (device-bar Package selector + `package:`
      token now an alias of `proc:`)

## Open questions

None — source (log) and token (`proc:`) are decided above.
