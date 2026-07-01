# Plan: Live PID tracking for the package filter

- **Status:** Done  <!-- Draft | Approved | In progress | Done | Abandoned -->
- **Owner:** Vũ
- **Created:** 2026-06-30
- **Related:** follow-up to `package-filter.md` (its documented limitation)

## Goal

Keep a package filter working when the app **restarts**: detect the new process in
the live log and add its PID to the filter automatically, so the user doesn't have
to re-apply after every restart (the pidcat behavior).

## Background

`adb logcat` emits an ActivityManager line when a process starts, e.g.
`Start proc 12345:com.example.app/u0a123 for ...` (newer) or
`Start proc 12345:com.example.app ...`. If a package filter is active and one of
these names the filtered package, its PID should join the active PID set.

## Scope

- **In:** while streaming with a package filter active, watch incoming lines for a
  process-start matching the filtered package and add the new PID to the filter.
- **Out (non-goals):** removing PIDs when a process dies (stale PIDs are harmless —
  they simply stop matching); tracking when no filter is active.

## Design

| File | Layer | Change |
|---|---|---|
| `src/zlog/core/proc.py` (new) | core | `parse_proc_start(message: str) -> tuple[str, str] | None` — returns `(pid, package)` for a "Start proc …" line, else `None`. Pure, regex-based, testable. |
| `src/zlog/core/__init__.py` | core | export `parse_proc_start`. |
| `src/zlog/ui/main_window.py` | ui | Track the active filter: `self._filter_package: str | None` and `self._filter_pids: set[str]`, set in `apply_package_filter`, reset in `clear_package_filter`. In `on_batch`, if a package filter is active, scan the batch with `parse_proc_start`; when the package matches and the PID is new, add it and call `proxy.set_pids(self._filter_pids)` (+ a status note). |
| `tests/test_proc.py` (new) | tests | newer `pid:package/uid` format, older `pid:package` format, non-matching lines, wrong-package lines. |

## Architecture touch points

- **Threading:** the scan happens in `on_batch`, already on the main thread via the
  reader's `batch_ready` signal — no new threading, no widget access off-thread.
- **Model/proxy:** reuses the existing `set_pids`; master list untouched.
- **Dependency direction:** parsing is pure `core/proc.py`, imported by `ui`. `core`
  stays Qt-free and unit-testable.
- **Versioning:** no bump (release-only).

## Risks & regressions to check

- App restart while filtered: new PID is picked up and its lines appear.
- No filter active: proc-start lines are ignored (no behavior change).
- Wrong-package proc-start lines don't alter the filter.
- Parser handles both the newer (`/uid`) and older formats and ignores noise.
- No unbounded growth issue (PID set gains an entry per restart; negligible).

## Verification

- [x] `uv run pytest` (new `test_proc.py` green)
- [x] `uv run ruff check .` and `uv run ruff format --check .`
- [ ] Manual (with a device): filter an app, force-stop & relaunch it → its new logs
      keep showing without re-applying the filter

## Open questions

- Match the package **exactly** (proposed) vs prefix (to catch `:pkg:process` sub-procs)?
- Surface a status note when a new PID is picked up (proposed) vs stay silent?
