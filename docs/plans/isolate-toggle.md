# Plan: Quick "isolate this" toggle

- **Status:** Done
- **Owner:** unassigned
- **Created:** 2026-07-16
- **Related:** ROADMAP "Filtering & search" (P1),
  [quick-filter-pid-package.md](quick-filter-pid-package.md), [clear-filters.md](clear-filters.md)

## Goal

After this ships, right-clicking a line (or a shortcut on the selected row) and
choosing **Isolate** narrows the view to just that line's PID + tag in one click;
triggering it again restores the exact query that was active before — so
"just show me this one thing" no longer means hand-editing the query bar and
trying to remember what it said.

## Scope

- **In:** a context-menu action "Isolate" on a clicked row and a shortcut
  (`Ctrl+I`) for the currently-selected row; toggles between an isolated query
  (`pid:<pid> tag:<tag>`, or `pid:<pid>` alone if the row has no tag) and the
  prior query-bar text; menu label reflects state ("Isolate" vs "Show All").
- **Out (non-goals):** a stack of multiple isolate levels (undo/redo), isolating
  by other fields (level, package name), persisting isolate state across
  restarts/sessions.

## Design

| File | Layer | Change |
|---|---|---|
| `src/zlog/ui/main_window.py` | ui | New state: `self._isolate_prev_query: str \| None = None` (init near other filter state, e.g. by `self._query_package`). New `_toggle_isolate(entry: LogEntry \| None) -> None`: if `self._isolate_prev_query is None` (not currently isolated) — need an `entry`; if none, no-op — save `self._isolate_prev_query = self.query.text()`, build the token string (`pid:` + optional ` tag:`), call `self._set_query_text(token_string)`. If already isolated, restore: `self._set_query_text(self._isolate_prev_query)`, then `self._isolate_prev_query = None`. Wire a `Ctrl+I` `QAction` (top-level, not menu-only, so it works from the table without opening a menu) calling `self._toggle_isolate(self._current_entry())` where `_current_entry()` reads `self.table.currentIndex()` the same way `_toggle_bookmark` does. In `_show_table_menu` (line 1890), add an "Isolate" / "Show All" action (label depends on `self._isolate_prev_query is None`) right after the "Filter to…"/"Exclude…" submenus, using the row under the cursor (already resolved into `entry` at line 1905) rather than the current selection — matches how the rest of that menu operates on the clicked row. |
| `src/zlog/ui/main_window.py` | ui | `_schedule_query_apply` (line 1250, fires only on real user keystrokes — programmatic `_set_query_text` calls `blockSignals` around `setText`, so they don't retrigger it): clear `self._isolate_prev_query = None` there. Rationale below. |
| `tests/test_main_window_settings.py` (or a new `test_isolate.py`-style block) | tests | Toggle isolate on a row with pid+tag → query bar reads `pid:<x> tag:<y>`; toggle again → query bar restores the original text; typing in the query bar after isolating clears the "restore" state (so a later toggle attempt is a no-op, not a stale restore). |

## Architecture touch points

- **Single wiring point preserved:** isolating and restoring both go through
  `_set_query_text` → `_apply_query`, the one place filtering is applied — no
  second filter path, no direct proxy setter calls from this feature.
- **Why clear on real typing:** if the user isolates, then manually edits the
  query bar (adding another token, say), a later "Show All" click would
  silently discard that manual edit and jump back to the pre-isolate text —
  surprising. Clearing the saved state on the first real keystroke means
  "Show All" only ever appears while the isolated query is still exactly what
  the toggle put there; after any manual edit the action reverts to "Isolate"
  (isolating again just overwrites the now-stale saved text with the current
  one, same as a fresh isolate).
- **No proxy/model changes** — this is pure query-bar orchestration in the ui
  layer; `core/query.py`/`LogFilterProxy` are untouched.

## Risks & regressions to check

- **No selection / no PID on the row** (e.g. a banner line): `Ctrl+I` and the
  context-menu action are no-ops (or disabled), never isolate to an empty
  `pid:` token.
- **Isolating twice in a row without restoring:** the second isolate call must
  not overwrite `_isolate_prev_query` with the already-isolated text — only the
  *first* isolate saves the prior query; the toggle logic (`is None` check)
  already guarantees this.
- **Clear Filters while isolated:** `clear_filters()` (line 995) resets the
  query bar directly — should also clear `_isolate_prev_query` so a later
  "Show All" doesn't resurrect a query the user explicitly cleared.
- **Session/tab switching while isolated:** switching tabs restores a
  per-session query via `_set_query_text` (line 248) — confirm this also
  resets `_isolate_prev_query` (it's `MainWindow`-level state, not per-session,
  so a stale isolate from tab A could leak into tab B's "Show All" otherwise).

## Verification

- [x] `uv run pytest` (340 passed; 1 pre-existing unrelated timing flake, see
      crash-anr-detector.md)
- [x] `uv run ruff check .` and `uv run ruff format --check .`
- [x] Smoke / screenshot via `run-zlog` (new `isolate` scenario): query bar
      reads `pid:1287 tag:AndroidRuntime`, "Showing 8 of 28 lines"
- [x] Manual: `tests/test_isolate.py` covers isolate → restore round-trip, a
      no-selection no-op, manual-edit clearing the restore state, and
      `clear_filters()` clearing it too

## Open questions

None.
