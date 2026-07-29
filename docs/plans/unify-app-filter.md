# Plan: One app filter (merge Focus App into Load/Apply)

- **Status:** Done  <!-- Draft | Approved | In progress | Done | Abandoned -->
- **Owner:** unassigned
- **Created:** 2026-07-24
- **Related:** [windows-app-focus.md](windows-app-focus.md), [package-filter.md](package-filter.md), [local-source-in-device-box.md](local-source-in-device-box.md)

## Goal

Filter to one app with a single control, whatever you're capturing: the package
box's **Load** offers both the processes seen in the log *and* the ones running on
this PC, and **Apply** filters to whichever you pick.

## Why

They already do the same job by the same means — both end at a `proc:` token in
the query — and differ only in where the candidate names come from:

| | Candidates | Action |
|---|---|---|
| **Load / Apply** (package box) | names parsed out of the current log | writes `proc:<name>` |
| **Focus App…** (button) | live running Windows processes | writes `proc:<name>` or `pid:<n>` |

So the user sees two controls for one intent, and which one works depends on
whether the app has logged anything yet. Merging follows the same instinct as
folding the Windows capture into the device box: one gesture, more sources.

## Scope

- **In:** `load_packages` merges log-derived names with running-process names
  (Windows), deduped and marked; the **Focus App…** button becomes **Browse…**
  next to the package box, opening the existing searchable picker (which keeps
  PID-exact focus for a long list); one shared "apply a target" path.
- **Out (non-goals):** removing the picker dialog, changing the `proc:`/`pid:`
  query syntax, process enumeration on non-Windows, and auto-refreshing the list
  while it's open.

## Design

The merge is mostly in the **candidate list**; both paths already converge on
`core.procinfo.focus_query`, so the "apply" half is one call.

| File | Layer | Change |
|---|---|---|
| `src/zlog/core/procinfo.py` | core | `merge_candidates(log_names, running) -> list[str]` — union of the two, case-insensitively deduped, sorted; a name that's **both** in the log and currently running is marked (e.g. `myapp.exe ●`) so you can tell live from historical. A `strip_marker(text)` companion so Apply/typing tolerates the marker. Pure, unit-tested. |
| `src/zlog/ui/main_window.py` | ui | `load_packages` builds from `model.process_names()` **+** `winlog.processes.list_processes()` (empty off Windows) via `merge_candidates`; the status line says where they came from ("12 from the log, 180 running"). `apply_package_filter` runs the text through `strip_marker` before building the token. `focus_app` keeps its dialog but is renamed in the UI to **Browse…**, and on accept writes into the package box **and** applies — so both routes end in the same place. |
| `src/zlog/ui/build.py` | ui | Relabel `focus_app_btn` to "Browse…" and move it next to Load/Apply/Clear so the row reads as one control group. |
| `docs/GUIDE.md` | — | Rewrite the two separate explanations as one "filter to an app" flow. |
| `tests/test_procinfo.py`, `tests/test_app_focus.py`, `tests/test_package_selector.py` | — | Pure: merge dedupes case-insensitively, marks the overlap, sorts, and survives either side being empty; `strip_marker` round-trips. Window: Load includes running processes (monkeypatched) and log names; Apply on a marked entry produces a clean `proc:` token; Browse… still applies. |

## Architecture touch points

- **Threading:** none. `list_processes()` is a synchronous snapshot, already used
  by the picker; it runs on demand from **Load**, not on a timer.
- **Model/proxy:** none — the filter is still a query token.
- **Dependency direction:** merging/marking is Qt-free in `core/procinfo.py`;
  `ui` supplies both lists. `ui → winlog → core` holds.

## Risks & regressions to check

- **The marker must never reach the query.** `proc:myapp.exe ●` would match
  nothing — `strip_marker` has to run on Apply, on Enter in the combo, and on the
  dialog's write-back. This is the most likely bug.
- **Enumeration cost on Load:** ~200 processes is fine, but Load is now doing
  real work on Windows; keep it snappy and don't call it per keystroke.
- **Off Windows** the running list is empty, so behaviour must be exactly as
  today (log names only) — no empty section, no error.
- **Existing tests** assert `load_packages` fills purely from the log and that
  `focus_app_btn` exists by that name; both change — update deliberately.
- **The `proc:` token's meaning is unchanged** (it matches the log's resolved
  process name), so a name that's running but has never logged will simply match
  nothing yet. Worth saying in the status line rather than looking broken.
- Package box is editable: typing a name that's in neither list must still work.

## Verification

- [x] `uv run pytest` (merge/dedupe/marker purity + the window paths) — 696 passed
      (3 pre-existing failures in `test_main_window_settings.py` unrelated to this
      change, confirmed by reproducing them on a stashed clean `main`)
- [x] `uv run ruff check .` and `uv run ruff format --check .`
- [x] `run-zlog` screenshot of the unified row (`smoke-idle.png`)
- [x] Manual on Windows: added a `driver.py app-filter-merged` scenario that runs
      the real (unmocked) `winlog.processes.list_processes()` on this machine —
      Load merged 2 log names with 391 real running processes, correctly marking
      the one overlap (`explorer.exe ●`); status line read "2 from the log, 391
      running." Apply/Browse… paths are covered by the window tests
      (`test_apply_strips_running_marker`, `test_focus_app_sets_query_by_name`).

## Decisions

- **Marker glyph:** `●` suffix (e.g. `myapp.exe ●`), matching the tab bar's
  live-session marker. Meaning is spelled out in the tooltip/status line.
- **Label:** rename "Package" to **"App"** throughout the UI (box label, button
  tooltips, status-line wording) since it now spans Android packages and Windows
  processes.
- **Load auto-run:** stays explicit — Load is not triggered automatically when a
  Windows capture starts.
