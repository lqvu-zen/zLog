# Plan: Package / PID filter

- **Status:** Done  <!-- Draft | Approved | In progress | Done | Abandoned -->
- **Owner:** Vũ
- **Created:** 2026-06-30
- **Related:** `device-picker.md` (Done — package PIDs are resolved on the selected device)

## Goal

Let the user narrow the view to a single app: pick a package, and zLog shows only
the log lines coming from that app's process(es).

## Background

Android log lines carry a **PID**, not a package name. So "filter by package" means
*resolve the package to its current PID(s)* and then keep only rows whose `pid` is in
that set. PIDs are resolved on the device with `adb -s <serial> shell pidof <package>`.
This is the same approach pidcat/plog use.

## Scope

- **In:**
  - A **Package** input in the toolbar (editable combo) — type a package, or pick
    from a list populated on demand from `pm list packages -3` (third-party apps).
  - Resolve the chosen package to PID(s) on the selected device and filter the table
    to those PIDs (combined with the existing level + text filters).
  - A **Clear** affordance that removes the package filter and restores the full view.
  - Sensible handling when the package isn't running (empty PID set) and when no
    device is selected.
- **Out (non-goals, future plans):**
  - **Auto-tracking app restarts.** When an app restarts its PID changes; v1 requires
    the user to re-apply the filter. A future plan can watch logcat's
    `Start proc <pid>:<pkg>` lines (pidcat-style) to update PIDs live.
  - Filtering by an arbitrary raw PID typed by hand (the package flow covers the need).
  - `ps`-based resolution for ancient devices (pidof is standard on modern Android).

## Design

| File | Layer | Change |
|---|---|---|
| `src/zlog/core/packages.py` (new) | core | `parse_pids(output: str) -> list[str]` (parses `pidof` output — space/newline separated); `parse_packages(output: str) -> list[str]` (parses `pm list packages` lines like `package:com.example` → `com.example`, sorted). Pure, testable. |
| `src/zlog/adb/packages.py` (new) | adb | `resolve_pids(serial, package, adb_path="adb", timeout=5)` runs `adb [-s serial] shell pidof <package>` → `parse_pids`; `list_packages(serial, adb_path, timeout=10)` runs `pm list packages -3` → `parse_packages`. |
| `src/zlog/ui/log_model.py` | ui | `LogFilterProxy` gains `_pids: set[str] | None` and `set_pids(pids)` (calls `invalidateFilter`). `filterAcceptsRow` adds a PID gate: when `_pids` is set, keep a row only if `entry.pid in _pids`. (Unparsed lines have `pid == ""` and are hidden while a package filter is active.) |
| `src/zlog/ui/main_window.py` | ui | Toolbar: a **Package** editable `QComboBox` + a small **▾** "load packages" action + an **×/Clear** for the package filter. Applying resolves PIDs for the current device and calls `proxy.set_pids(...)`; clearing calls `proxy.set_pids(None)`. Status-bar feedback. |
| `tests/test_packages.py` (new) | tests | `parse_pids` (single/multiple/empty/whitespace) and `parse_packages` (prefix stripping, blank/sorted, ignores junk). |
| `.claude/skills/run-zlog/scripts/driver.py` | (skill) | A `package-filter` scenario: seed rows with two PIDs, call `proxy.set_pids({one})`, screenshot the narrowed view. |

### UI behavior

- **Applying:** with a device selected, choosing/typing a package and pressing
  Enter (or an Apply button) resolves PIDs and filters. Status: `Showing com.x
  (pid 1287)` or `Showing com.x (pids 1287, 1342)`.
- **Not running / no PIDs:** don't blank the view — leave the filter unset and show
  `com.x isn't running — start it and apply again`.
- **No device selected:** the Package control is disabled (resolving needs a device).
- **Clear:** removes the PID filter; the full stream is visible again instantly
  (proxy only — master list untouched).
- **Loading the package list** is optional and on demand (it can take a second on
  some devices), so the combo is usable as a plain text field without it.

## Architecture touch points

- **Threading:** `resolve_pids` and `list_packages` are short, one-shot `adb shell`
  calls — run **synchronously on the main thread** with a timeout, exactly like
  `list_devices` from the device-picker plan. They return data; they never touch
  widgets off-thread. The only long-running work (the logcat stream) stays in
  `AdbReader` (`QThread`) reaching the UI via signals. *Risk/fallback:* same as
  device listing — if `pm list packages` feels slow, a later plan moves it to a
  `QThread`; noted as a non-goal here.
- **Model/proxy:** this is the canonical "new filter predicate" extension —
  `filterAcceptsRow` + `set_pids` + `invalidateFilter`. The master list (`_rows`)
  stays complete, so clearing the package filter is instant.
- **Dependency direction:** `core/packages` (pure) ← `adb/packages` ← `ui`; the proxy
  lives in `ui`. All arrows stay one-way (`ui → adb → core`).
- **Colors/theme:** none.

## Risks & regressions to check

- All three filters (package PIDs + min level + text) combine with AND; verify.
- Clearing the package filter restores the full view immediately.
- Package not running → friendly hint, view not blanked.
- App restart → stale PIDs (documented limitation; re-apply). Verify no crash.
- Unparsed/banner lines (pid `""`) are hidden while a package filter is active — by
  design; confirm that's acceptable.
- Device selected vs streaming: resolving PIDs works whether or not streaming is
  live (it's a separate `adb shell` call).

## Verification

- [x] `uv run pytest` (new `test_packages.py` green)
- [x] `uv run ruff check .` and `uv run ruff format --check .`
- [x] `run-zlog` `package-filter` scenario screenshot shows only the chosen PID's rows
- [ ] Manual (with a device): load packages, pick one running app, see only its logs;
      Clear restores all
- [ ] Manual: apply a package that isn't running → hint shown, view not blanked

## Open questions

- Package control as an **editable combo** (type or pick) — agreed? Proposed: yes.
- Resolve PIDs with **`pidof`** (proposed) vs parsing `ps`? pidof is simpler and
  standard on modern Android.
- Auto-track app restarts now or later? Proposed: **later** (non-goal here).
