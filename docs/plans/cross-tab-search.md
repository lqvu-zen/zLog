# Plan: Search across all open tabs

- **Status:** Done  <!-- Draft | Approved | In progress | Done | Abandoned -->
- **Owner:** unassigned
- **Created:** 2026-08-20
- **Related:** [device-tabs.md](device-tabs.md), [saved-filters-sidebar.md](saved-filters-sidebar.md)

## Goal

Run one query against every open tab at once and see matching lines grouped by
tab, instead of switching tabs one at a time to check each — useful once
several device/file/app tabs are open at the same time (`device-tabs.md`).

## Scope

- **In:** a "Search All &Tabs…" command (View menu, `Ctrl+Shift+F`) that runs the
  query-bar syntax against every session's full row list (not just the active
  tab's filtered view), lists matches grouped by tab, double-click jumps to that
  tab and row.
- **Out (non-goals):** editing or acting on multiple tabs' filters at once (that
  role already belongs to per-tab query + Saved Filters); a standing "global
  filter" that stays applied across tabs — this is deliberately a one-shot,
  read-only search dialog, not a second parallel filtering system next to the
  per-tab proxy.

## Design

| File | Layer | Change |
|---|---|---|
| `src/zlog/core/logfilter.py` | core | **Reused as-is** — `build_predicate(spec, case)` (`core/logfilter.py:22`) already turns a `QuerySpec` into a plain `LogEntry -> bool` callable, built for exactly this "filter headlessly, no proxy" need (today used by CLI tail mode). This plan's whole value is that the predicate logic already exists and doesn't need reinventing. |
| `src/zlog/ui/log_model.py` | ui | **No change needed** — `all_entries()` (`log_model.py:369-371`) already returns `list(self._rows)`, exactly the accessor this plan sketched adding. |
| `src/zlog/ui/cross_tab_search.py` (new) | ui | `search_sessions(sessions, spec, case) -> list[TabMatch]`: for each session, `build_predicate(spec, case)` then filter `session.model.rows()`, keeping (session, source_row, entry) tuples. Thin — the real logic is `build_predicate`, already core and already tested. |
| `src/zlog/ui/cross_tab_search_dialog.py` (new) | ui | Query input (reuse `QueryLineEdit`/completion popup if practical) + a results table (tab name, entry summary); double-click activates that tab and scrolls the table to the matched row (reuse whatever `_goto_bookmark`/`_goto_incident`-style jump helper already exists for "activate a row by source index"). |
| `src/zlog/ui/main_window.py` | ui | `_search_all_tabs()` slot wiring the dialog to `self._sessions`. |
| `src/zlog/ui/menus.py` | ui | New View-menu action + shortcut. |
| `tests/test_cross_tab_search.py` (new) | — | `search_sessions` against stub sessions/models: matches found in the right tab, no matches, a query using a gate `build_predicate` doesn't support (e.g. `since:`) doesn't crash — it's silently ignored, same documented limitation `core/logfilter.py`'s docstring already states for the CLI. |

## Architecture touch points

- **Model/proxy:** no new filter predicate — this deliberately reuses
  `core/logfilter.py` rather than duplicating `LogFilterProxy.filterAcceptsRow`'s
  gates a second time. Any future gate added to the proxy that isn't also added
  to `core/logfilter.py` will silently not apply here — call this out at the top
  of `logfilter.py` if it isn't already.
- **Dependency direction:** `core/logfilter.py` untouched and Qt-free; the new
  `ui/cross_tab_search.py` only reads from sessions it's handed, never reaches
  into `main_window` internals.
- **Threading:** none — this runs synchronously on the UI thread against
  already-captured rows. For a very large multi-tab capture this could be slow;
  see Risks.

## Risks & regressions to check

- **`core/logfilter.py`'s documented gap:** `proc:`/`since:`/`until:` are
  GUI-only (need the live PID→name map / a clock) and are silently ignored by
  `build_predicate` (`core/logfilter.py:9-10`). A cross-tab search using those
  tokens will behave differently from a same-tab query-bar search using the
  identical text — this must be visible in the dialog (e.g. a note when the
  query contains an ignored token), not a silent surprise.
- **Cost of scanning every row of every open tab synchronously** on the UI
  thread — for a handful of tabs at typical sizes this is fine, but a search
  across several million-row tabs could visibly freeze the dialog. Consider
  showing a busy cursor and bounding total matches returned (e.g. cap per tab)
  rather than assuming it's always cheap.
- **`rows()` copying the full list per tab per search** — fine at today's
  scale; note it as the first thing to revisit if this gets slow.

## Verification

- [x] `uv run pytest` — `tests/test_cross_tab_search.py` (pure `search_sessions`/
      `unsupported_gates` cases, stubbed sessions) and
      `tests/test_main_window_tabs.py::test_search_all_tabs_jumps_to_matching_tab`
      / `test_search_all_tabs_flags_unsupported_gates` — all green.
- [x] `uv run ruff check .` / `ruff format --check .` clean.
- [x] Manual (`run-zlog` `search-all-tabs` scenario, screenshotted): two tabs
      seeded, a term matching rows in the background tab found and grouped
      under that tab's name with correct line numbers; the double-click → jump
      path itself is covered by the automated test above (activates the tab
      via `tab_bar.setCurrentIndex`, re-roots `model`/`proxy`, selects the row).
- [x] Covered by `test_search_all_tabs_flags_unsupported_gates` and
      `test_unsupported_gates_flagged_without_crashing`: `proc:`/`since:` are
      flagged, and the search still runs rather than crashing or silently
      matching everything.

## Open questions

- **Reuse the query bar's completion popup in the search dialog**, or keep it a
  plain line edit for v1? **Resolved: plain `QLineEdit`** for v1, as leaned —
  the completion popup is wired specifically to the active session's live
  tag/pid/proc values, which doesn't generalize cleanly across tabs.
- **Cap match count per tab** — what's a sane default before this needs testing
  against a real large capture? **Resolved differently than sketched:** capped
  the *total displayed* rows at 2000 (`_MAX_RESULTS` in
  `cross_tab_search_dialog.py`) rather than per-tab, with a hint line when
  truncated. `search_sessions` itself returns every match uncapped — only the
  dialog's table population is bounded, so a future caller (e.g. exporting all
  matches) isn't limited by the display cap. Revisit if a real large-capture
  test shows this isn't the right knob.
