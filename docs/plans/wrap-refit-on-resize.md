# Plan: Wrap re-fit on resize

- **Status:** Done  <!-- Draft | Approved | In progress | Done | Abandoned -->
- **Owner:** Claude
- **Created:** 2026-07-18
- **Related:** wrap-messages.md, inline-match-highlight.md

## Goal

When word-wrap is on, widening or narrowing the window (or dragging the
log/detail splitter, or toggling a dock) re-fits the visible wrapped rows to the
new width immediately — instead of leaving rows clipped or over-tall until the
next scroll.

## Scope

- **In:** re-run `_fit_visible_rows` (debounced) whenever the table's viewport
  width changes.
- **Out (non-goals):** re-fitting *all* rows (still O(visible) only, per the
  virtualization rule); any change to wrap layout itself.

## Design

`_fit_visible_rows` already exists and is debounced through `self._wrap_timer`
via `_schedule_wrap_fit`; today it's only triggered by scrollbar
`valueChanged` and the batch/append signals. A width change never fires either,
so wrapped heights go stale on resize. Add a `resized` signal to the view and
route it through the same debounce.

| File | Layer | Change |
|---|---|---|
| `src/zlog/ui/table_view.py` | ui | Add `resized = Signal()`; override `resizeEvent` to `super().resizeEvent(event)` then `self.resized.emit()`. |
| `src/zlog/ui/main_window.py` | ui | In `_connect_signals`, connect `self.table.resized` to `self._schedule_wrap_fit` (alongside the existing scrollbar connection at line ~839). |

## Architecture touch points

- **Threading:** none — pure UI event on the main thread.
- **Model/proxy:** none. Row heights only; the model stays virtualized.
- **Dependency direction:** unchanged (`ui` only).

## Risks & regressions to check

- `_schedule_wrap_fit` is a no-op when `wrap` is False (it guards on
  `self.log_delegate.wrap`), so non-wrap mode is unaffected and pays nothing.
- Resize fires rapidly during a drag; the 60 ms single-shot `_wrap_timer`
  already coalesces bursts into one fit, so no per-pixel churn.
- The first `resizeEvent` arrives during construction before `log_delegate`
  exists — guard: the connection is made in `_connect_signals` (after
  `_build_widgets`), and `_schedule_wrap_fit` reads `self.log_delegate.wrap`,
  which is set by then. Confirm no resize is emitted earlier.

## Verification

- [ ] `uv run pytest` (add a test: emitting `resized` in wrap mode grows a
      seeded long row; a unit test can call `_schedule_wrap_fit` + fire the timer).
- [ ] `uv run ruff check .` and `uv run ruff format --check .`
- [ ] `run-zlog` driver scenario `wrap-refit`: seed a long message, wrap on,
      resize narrow, screenshot shows the row re-fitted.

## Open questions

- None.
