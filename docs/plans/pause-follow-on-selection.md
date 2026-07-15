# Plan: Pause Follow while a row is selected

- **Status:** Done
- **Owner:** unassigned
- **Created:** 2026-07-15
- **Related:** [smart-follow.md](smart-follow.md) (scroll-up already pauses the
  yank; this closes the remaining gap), [pause-autoscroll.md](pause-autoscroll.md),
  [jump-to-latest.md](jump-to-latest.md)

## Goal

With Follow on, clicking a row to inspect it (or navigating to one via F3/Ctrl+G/
bookmark-next) no longer gets yanked away by the next incoming batch — auto-scroll
only fires when the user is both scrolled to the bottom *and* has no row selected,
i.e. actually watching the live tail.

## Why (bug report)

`smart-follow.md` already stops the viewport yanking when the user scrolls up to
read (`was_at_bottom` goes false as soon as the scrollbar lags behind the growing
`maximum`) — that part works and is tested
(`test_follow_stays_manual_and_never_yanks`). But `_on_batch` computes
`was_at_bottom` from the scrollbar position alone. Selecting a row (a click, or
any of the goto/match/bookmark navigation actions) doesn't move the scrollbar, so
if the user was already at the bottom when they selected an older-look-relevant
row, the very next batch still sees `was_at_bottom == True` and calls
`scrollToBottom()`, yanking the just-selected row out of view. This is the
remaining case the user hit.

## Scope

- **In:** auto-scroll requires *both* "scrolled to the bottom" and "no active
  selection." Selecting any row (by click or by any existing navigation action —
  F3/Shift+F3 match nav, Ctrl+G goto, bookmark next/prev) pauses the next
  auto-scroll the same way scrolling up already does. No new state needs to be
  tracked: both `_on_batch` and the coalesced `_do_follow_scroll` timer callback
  re-check `hasSelection()` fresh each time, exactly like the existing scrollbar
  check.
- **Out:** distinguishing "selected the newest row" as a special case that keeps
  tailing (adds complexity for a marginal case); auto-clearing the selection from
  any button (Latest, Clear, etc.) — resuming still requires the user to scroll
  back to the bottom themselves (or clear the selection and be at the bottom),
  matching the existing pattern for scroll-based pause/resume.

## Design

| File | Layer | Change |
|---|---|---|
| `src/zlog/ui/main_window.py` | ui | In `_on_batch`, change `was_at_bottom = sb.value() >= sb.maximum() - 4` to also require `not self.table.selectionModel().hasSelection()`. In `_do_follow_scroll` (the single-shot timer's fire callback), add the same `hasSelection()` guard before calling `scrollToBottom()` — closes the small race where a batch arms the timer while at the bottom, then the user selects a row before the 80ms timer fires. |

## Architecture touch points

- UI-only; no threading, model, or proxy change. Reuses `self.table.selectionModel()`,
  already used elsewhere (`_selected_entries`, `_update_detail`).
- No new state to persist — both gates are recomputed fresh per batch/timer-fire,
  the same pattern the existing scrollbar check already uses.

## Risks & regressions to check

- Selecting a row while scrolled to the bottom: the next batch must not move the
  viewport (the core bug being fixed).
- Clearing the selection (e.g. clicking empty space) while already scrolled to the
  bottom: the next batch resumes tailing normally.
- Existing scroll-up-pauses / scroll-to-bottom-resumes behavior
  (`test_follow_stays_manual_and_never_yanks`) must keep passing unchanged when no
  selection is involved.
- Match-nav (F3), Ctrl+G, and bookmark-next all call `selectRow`/`setCurrentIndex`
  — each of these should now also pause the next auto-scroll, since they all put
  the user's attention on a specific row.

## Verification

- [x] `uv run pytest` (new case: select a row while at the bottom, batch arrives,
      viewport must not move; clearing selection at the bottom resumes tailing)
- [x] `uv run ruff check .` and `uv run ruff format --check .`
- [x] Headless smoke: app renders with no regressions (`run-zlog` driver)

## Open questions

- None blocking.
