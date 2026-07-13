# Plan: Severity navigation (jump to next/prev problem)

- **Status:** Done
- **Owner:** unassigned
- **Created:** 2026-07-11
- **Related:** ROADMAP v1.4 "Reading & analysis", [match-navigation.md](match-navigation.md),
  [bookmarks.md](bookmarks.md)

## Goal

After this ships, F2 / Shift+F2 (and View → Next/Previous Problem) jump the
selection to the next/previous **warning-or-above** line in the current view,
wrapping around — so triaging errors in a noisy log is a keypress, not a scroll.

## Scope

- **In:** jump to the next/previous visible row with level rank ≥ Warning; F2 /
  Shift+F2 shortcuts + two View menu items; wrap-around; respects the active filter
  (operates on visible/proxy rows).
- **Out:** a configurable threshold, a severity minimap (that's scrollbar heat
  marks, a separate item), counting problems in the status bar.

## Design

| File | Layer | Change |
|---|---|---|
| `src/zlog/ui/main_window.py` | ui | Import `LEVEL_RANK`. `_goto_severity(step)` scans proxy rows from the current one (forward/backward, then wraps) for the first with `entry.rank >= LEVEL_RANK["W"]` and selects/scrolls to it (same select+scroll as `_goto_bookmark`). Helper `_proxy_rank(row)` maps a proxy row to its entry's rank. Wire F2/Shift+F2 shortcuts and View → **Next Problem** / **Previous Problem**. |
| `tests/test_main_window_settings.py` | tests | With I/W/I/E rows, forward stops on W then E then wraps to W; backward wraps to E. |

## Architecture touch points

- **Proxy-based:** navigation is over visible rows, so it honors level/tag/search
  filters automatically.
- **Early-exit scan:** walks from the cursor and stops at the first match (fast even
  on large logs) rather than materializing all problem rows.

## Risks & regressions to check

- **Empty / no-problem view:** no selection change, no crash.
- **No current selection:** treat as before-row-0 so forward finds the first
  problem.
- **Wrap-around:** forward past the last problem returns to the first; backward
  mirrors.

## Verification

- [ ] `uv run pytest`
- [ ] `uv run ruff check .` and `uv run ruff format --check .`
- [ ] Manual: F2 through a log hops error/warning to error/warning.
