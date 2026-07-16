# Plan: Crash / ANR detector

- **Status:** Done
- **Owner:** unassigned
- **Created:** 2026-07-16
- **Related:** ROADMAP "Analysis & insight" (P1), [severity-navigation.md](severity-navigation.md),
  [bookmarks.md](bookmarks.md), [error-sparkline.md](error-sparkline.md)

## Goal

After this ships, the status bar shows a live count of detected crash/ANR
incidents in the current capture, and **Next Incident** / **Previous Incident**
(View menu + shortcut) jump the selection straight to each one — so finding "did
this app crash, and where" is a glance and a keypress instead of scrolling or
writing a regex.

## Scope

- **In:** classify each appended line as `crash`, `anr`, or neither, using fixed
  Android logcat markers (`FATAL EXCEPTION`, `Fatal signal <n>`, `ANR in `);
  maintain a running count; a status-bar badge; next/prev navigation over
  **visible** (proxy) rows, wrapping, mirroring `_goto_severity`/`_goto_bookmark`.
- **Out (non-goals):** a dialog/list of incidents (Tag Summary already covers
  browsing by tag), a visual row marker/decoration, configurable detection
  patterns, stack-trace folding (separate backlog item), persisting incident
  state across sessions.

## Design

| File | Layer | Change |
|---|---|---|
| `src/zlog/core/incidents.py` (new) | core | `classify_incident(entry: LogEntry) -> str \| None` — regex over `entry.message` only (tag varies across OEMs/native crashes; the message markers don't): `FATAL EXCEPTION` → `"crash"`, `Fatal signal \d+` → `"crash"`, `ANR in ` → `"anr"`, else `None`. `format_incident_summary(counts: Mapping[str, int]) -> str` — e.g. `"2 crashes, 1 ANR"`, `""` when empty (mirrors `format_level_summary`). |
| `src/zlog/ui/log_model.py` | ui | `LogTableModel.__init__`: add `self._incidents: dict[int, str] = {}` (source row → kind). `append_entries`: for each new entry, call `classify_incident` and record its row if not `None`. `_enforce_cap`: shift/drop incident rows the same way `_bookmarks` is remapped. `clear()`: clear `_incidents`. New accessors: `incident_rows() -> list[int]` (sorted keys), `incident_counts() -> Counter` (kind → count). |
| `src/zlog/ui/main_window.py` | ui | New `self.incident_label = QLabel("")` added via `addPermanentWidget` next to `count_label`; updated inside `_update_counts` (already debounced via `_counts_timer`, and the incident dict is maintained incrementally so this stays O(1) — no new timer needed). `_goto_incident(step)`: same shape as `_goto_bookmark` — map `model.incident_rows()` through `proxy.mapFromSource`, skip rows hidden by the current filter, find next/prev from the current selection, wrap. Two View-menu actions "Next Incident" / "Previous Incident" (shortcuts `Alt+F2` / `Alt+Shift+F2`, free — `F2`/`Shift+F2` is problem-nav, `Ctrl+F2`/`Ctrl+Shift+F2` is bookmark-nav), placed after the bookmark group. |
| `tests/test_log_model.py` | tests | Append entries containing a `FATAL EXCEPTION` line, an `ANR in` line, and plain lines; assert `incident_rows()` and `incident_counts()`. A max-rows test mirroring `test_max_rows_remaps_bookmarks` for the remap/drop path. |
| `tests/test_incidents.py` (new) | tests | Unit tests for `classify_incident`/`format_incident_summary` directly (Qt-free). |

## Architecture touch points

- **Qt-free core:** classification and summary formatting live in `core/incidents.py`
  with zero Qt imports, unit-tested directly — mirrors `core/models.py`'s
  `rank`/`LEVEL_RANK` split from the UI that consumes it.
- **Incremental, not a rescan:** incidents are classified once per line as it's
  appended (same loop that already updates `_level_counts`/`_pid_names`), so the
  running count is O(1) per batch, not an O(n) scan — keeps `Start` responsive on
  a busy device (see `perf-start-freeze.md`).
- **Proxy-based navigation:** `_goto_incident` walks `incident_rows()` mapped
  through the proxy, so it honors the active level/tag/search/package filters,
  exactly like `_goto_bookmark`.
- **Ring-buffer cap:** `_enforce_cap` must remap `_incidents` the same way it
  remaps `_bookmarks` (shift by `overflow`, drop rows that fell off), or indices
  would point at the wrong row after a cap trims old lines.
- **Dependency direction (`ui → adb → core`)** holds: `log_model.py` (ui) imports
  the new `core/incidents.py`; `core` imports nothing new.

## Risks & regressions to check

- **False positives:** message-only matching could theoretically match a line
  that merely *mentions* "ANR in" in an unrelated string (e.g. user app log text)
  — accepted risk, same class of heuristic as the existing crash/ANR literature;
  not worth a stricter parser for v1.
- **Cap/clear interaction:** clearing the log or hitting the ring-buffer cap must
  leave `incident_rows()`/`incident_counts()` consistent (no stale indices, no
  negative counts) — covered by the remap test above, same shape as bookmarks.
- **Empty/no-incident log:** badge shows nothing (empty string, no "0 crashes"
  clutter); Next/Previous Incident are no-ops, no crash.
- **Filtered view:** an incident hidden by the current filter must be skipped by
  navigation (mirrors bookmark nav's `proxy_row >= 0` check) rather than jumping
  to a row the user can't see.

## Verification

- [x] `uv run pytest` (325 passed; 1 pre-existing unrelated timing flake in
      `test_follow_stays_manual_and_never_yanks`, confirmed failing on `main`
      before this change too)
- [x] `uv run ruff check .` and `uv run ruff format --check .`
- [x] Smoke / screenshot via `run-zlog` (new `incidents` scenario) showing the
      status-bar badge ("3 crashes") with a capture that includes
      `FATAL EXCEPTION` lines, and `_goto_incident(1)` landing on the first one
- [x] Manual: `_goto_incident` verified via the driver scenario; wrap-around
      logic mirrors `_goto_bookmark`, already covered by that pattern in
      practice

## Open questions

None — scope and detection patterns are fixed above; flag during review if a
narrower/broader pattern set is wanted.
