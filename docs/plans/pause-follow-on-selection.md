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
  tailing (adds complexity for a marginal case).

**Revised after shipping:** the first cut left resuming broken — once a row was
selected, `hasSelection()` stayed true forever, so scrolling back to the bottom
never resumed tailing until the user *also* manually deselected. See "Update"
below.

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

## Update: auto-clear the selection on resume (2026-07-15)

**Bug:** scrolling back to the newest line still left Follow paused, because
nothing ever cleared a lingering selection — `hasSelection()` stayed true
indefinitely, so the `not hasSelection()` gate never passed again.

**Fix:** the user manually scrolling back to the bottom is itself treated as
"resume tailing," which now clears the stale selection so the existing gate
naturally reopens on the next batch.

| File | Layer | Change |
|---|---|---|
| `src/zlog/ui/main_window.py` | ui | `to_latest_btn` now calls a new `_jump_to_latest()` (clears the selection, then `scrollToBottom()`) instead of `scrollToBottom` directly — an explicit "go to now." For a plain manual scroll (dragging the scrollbar, wheel, keyboard), `verticalScrollBar().valueChanged` is wired to `_maybe_resume_follow_on_scroll`: if the value reaches the bottom *and* a row is selected, it clears the selection. |
| `src/zlog/ui/main_window.py` | ui | The tricky part is telling a genuine user scroll apart from the scrollbar's own "scroll the row into view" side effect of a selection change (click, or F3/Ctrl+G/bookmark-next) — that side-effect scroll must *not* immediately clear the selection it was triggered by. `_rebind_selection` connects `currentChanged`/`selectionChanged` to `_arm_scroll_clear_suppression`, which sets `_suppress_next_scroll_clear = True` and self-disarms via `QTimer.singleShot(0, ...)`. A selection that needs no scroll (already fully visible — the common case) never emits `valueChanged` at all, so the self-disarm (not a "consume on next scroll") is what keeps the flag from lingering and wrongly swallowing a later, unrelated scroll. |

**Risk covered:** a selection made on a row that's already fully on-screen
induces no scroll to consume the suppression flag — verified by
`test_follow_resumes_on_scroll_to_bottom_without_manually_deselecting`, which
selects the last (already visible) row specifically to exercise that path.

**Verification (update):**
- [x] `uv run pytest` (new: scrolling to the bottom without manually
      deselecting resumes tailing; existing pause/resume-by-clearing test still
      passes)
- [x] `uv run ruff check .` / `format --check .`
- [x] Headless smoke: app renders with no regressions
