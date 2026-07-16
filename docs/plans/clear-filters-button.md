# Plan: Surface the "Clear filters" button

- **Status:** Done
- **Owner:** unassigned
- **Created:** 2026-07-16
- **Related:** [clear-filters.md](clear-filters.md) (the original feature/menu action)

## Goal

After this ships, there's a visible **Clear filters** button on the filter row
that resets every filter (level, search, tag, exclude, package, pid/proc,
time-range) in one click — so users don't have to open the View menu or clear the
query bar by hand.

## Scope

- **In:** place the already-built `self.clear_filters_btn` (created at
  `main_window.py:502`, wired to `clear_filters` at :883, but never added to a
  layout) onto the filter row, to the right of the match-navigation controls.
  Refresh its tooltip to reflect that it clears *all* filters.
- **Out (non-goals):** changing what `clear_filters()` does (it already clears
  everything via the query bar), removing the existing View → Clear Filters menu
  item (keep both entry points).

## Design

| File | Layer | Change |
|---|---|---|
| `src/zlog/ui/main_window.py` | ui | In `_build_layout`, after `filter_row.addWidget(self.match_label)`, add `filter_row.addWidget(self.clear_filters_btn)`. Update the tooltip (line 503) from "Reset level, search, and package filters" to "Reset all filters (level, search, tag, package, time…)". No new widget, signal, or method — the button object and its `clicked → clear_filters` connection already exist. |

## Architecture touch points

- **No model/proxy/threading involvement** — pure widget placement. `clear_filters`
  already routes through the single `_apply_query` path (clears the query bar),
  so every gate resets together; nothing new to wire.

## Risks & regressions to check

- **Layout crowding:** the filter row already holds the query box (stretchy) +
  match prev/next + label; the button appends at the right edge — confirm the
  query box still takes the slack and nothing overflows.
- **Duplicate entry points:** the View menu action and the button both call
  `clear_filters` — intended (button for discoverability, menu for keyboard
  users); no conflict.

## Verification

- [x] `uv run pytest` (384 passed; 1 pre-existing unrelated timing flake)
- [x] `uv run ruff check .` and `uv run ruff format --check .`
- [x] Smoke / screenshot via `run-zlog`: the **Clear filters** button now shows
      at the right end of the filter row (next to the match-nav `<`/`>`)
- [x] `clear_filters()` (unchanged) already clears every gate via the query bar;
      the button reuses its existing `clicked` connection

## Open questions

None — placement (right end of the filter row) is the obvious spot; flag in
review if a different location is preferred.
