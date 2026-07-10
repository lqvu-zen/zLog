# Plan: Smart follow (pause on scroll-up, resume at bottom)

- **Status:** Done
- **Owner:** unassigned
- **Created:** 2026-07-10
- **Related:** [pause-autoscroll.md](pause-autoscroll.md) (the initial simple
  toggle), [jump-to-latest.md](jump-to-latest.md)

## Goal

After this ships, Follow behaves like a proper log tail: while on, the view stays
pinned to the newest line; if the user scrolls up to read history, following
pauses automatically (no yank); scrolling back to the bottom resumes it. The
checkbox still works as a manual master toggle.

## Why (bug report: "follow not working / did we finish it?")

The original plan implemented only "scroll to bottom whenever Follow is checked."
It works, but it can't tell that the user scrolled up to read — so every incoming
batch drags them back to the bottom, making history unreadable while streaming.
The intended "auto-scroll only when at the bottom" behavior was never built. This
finishes it.

## Scope

- **In:** auto-sync the Follow checkbox to scroll position — uncheck when the user
  scrolls off the bottom, re-check when they return; keep pinning to bottom on new
  batches while checked; checking Follow (or pressing Latest) snaps to the newest.
- **Out:** a floating "resume tail" button, smoothing/animation, remembering a
  scroll offset across restarts.

## Design

| File | Layer | Change |
|---|---|---|
| `src/zlog/ui/main_window.py` | ui | Add `self._suppress_follow_sync = False` state. Connect the table's vertical `scrollBar().valueChanged` → `_sync_follow_to_scroll`, and `follow_check.toggled` → `_on_follow_toggled`. `_sync_follow_to_scroll`: if not suppressed, set `follow_check` to `value >= maximum` (at bottom) — this is what pauses/resumes on user scroll. `_on_follow_toggled(checked)`: if checked, snap to bottom. Wrap the whole of `on_batch` (append + optional `scrollToBottom`) in `_suppress_follow_sync = True/False` so model/scroll changes during a batch never toggle Follow — only genuine user scrolls do. |

## Architecture touch points

- **Threading/model:** unchanged — still main-thread `on_batch` from the reader
  signal; virtualization untouched.
- **Feedback-loop safety:** programmatic scrolls (batch tailing, toggle snap) run
  under `_suppress_follow_sync`, so only user-driven `valueChanged` flips Follow;
  the `isChecked() != at_bottom` guard prevents redundant toggles/recursion.

## Risks & regressions to check

- **No yank while reading:** with Follow paused (scrolled up), new batches must not
  move the viewport.
- **Resume:** scrolling to the bottom (or pressing Latest) re-checks Follow and
  tailing continues.
- **Ring-buffer trim:** top-row removal during a batch must not spuriously pause
  Follow — hence suppressing sync across the whole `on_batch`.
- **Settings:** Follow persists as before; auto-uncheck from reading history may
  save `follow=False` — acceptable.

## Verification

- [ ] `uv run pytest` (new test: follow pins to bottom; scroll-up pauses and blocks
      the yank; scroll-to-bottom resumes)
- [ ] `uv run ruff check .` and `uv run ruff format --check .`
- [ ] Manual: stream, scroll up (stays), scroll to bottom (resumes tailing).

## Implementation note (shipped, revised)

The first cut auto-toggled the **Follow** checkbox from scroll position, which was
confusing — a checkbox that changes itself as you scroll reads as broken. Shipped
instead: **Follow is a stable manual toggle**. `on_batch` captures whether the view
is at the bottom *before* appending and tails only when `follow_check` is checked
**and** the user was already at the bottom. Scrolling up to read is never yanked; on
returning to the bottom, tailing resumes on its own. No `valueChanged`/`toggled`
wiring and no self-changing checkbox.
