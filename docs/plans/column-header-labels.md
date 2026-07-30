# Plan: A thin header strip labeling the log's columns

- **Status:** Done  <!-- Draft | Approved | In progress | Done | Abandoned -->
- **Owner:** unassigned
- **Created:** 2026-07-30
- **Related:** [auto-hide-empty-columns.md](auto-hide-empty-columns.md), [logcat-style-ui.md](logcat-style-ui.md), [fixed-columns-middle-elide.md](fixed-columns-middle-elide.md)

## Goal

A labeled row above the log ("Time · PID·TID · Tag · [Process] · Lvl · Message")
so it's clear what each segment of the dense one-line-per-entry view is,
without reintroducing a real Qt grid.

## Why

The table's native header is hidden outright (`build.py`: `horizontalHeader()
.setVisible(False)`) — the six logical columns (`Time/PID/TID/Level/Tag/Message`,
`log_model.COLUMNS`) are all painted freehand by `LogItemDelegate` into a single
stretched Qt column, so there's nothing for a real header to attach to; showing
it as-is would label one wide column "Time" and nothing else. A new small
widget that mirrors the delegate's own width math is the only way to get labels
that actually line up with the segments — and depends on
[auto-hide-empty-columns.md](auto-hide-empty-columns.md) landing first, so a
hidden PID·TID/Tag segment doesn't get an orphaned label floating over the
message text.

## Scope

- **In:** a slim, fixed-height label strip between the filter bar and the log
  table, redrawn from the exact same column-width computation the delegate
  uses (so it can never drift out of sync with the rows themselves): reuses
  `LogItemDelegate._col_widths`/`_gutter_w`/`_msg_left` directly rather than
  re-deriving parallel math. Updates live with wrap/show-process/line-numbers,
  window resizing, theme, and the auto-hide state from the other plan.
- **Out (non-goals):** click-to-sort, resizable columns (nothing here defines
  real column boundaries the user can drag), a real `QHeaderView` (the
  delegate's freehand layout doesn't map onto one), changing `log_model.COLUMNS`
  or the Qt model's actual column count.

## Design

| File | Layer | Change |
|---|---|---|
| `src/zlog/ui/log_header_bar.py` (new) | ui | `LogHeaderBar(QWidget)`: holds a reference to the window's `LogItemDelegate` and source model (constructor args, like `HistogramBar`/`FilterChipBar`'s existing shape). Fixed `sizeHint` height (one line + small padding, from `QFontMetrics` on its own font — kept in sync with the table's font, see risks). `paintEvent` computes `gutter = delegate._gutter_w(...)`, `time_w, pid_w, tag_w, proc_w = delegate._col_widths(gutter, width, cw, model, fm)`, then draws "Time" / "PID·TID" / "Tag" / "Process" (only when `delegate.show_process`) / "Lvl" / "Message" at the same x-offsets `seg()` advances through — skipping any label whose width is `0` (the auto-hide case), exactly mirroring the delegate's own skip. Bottom border line for a visual seam against the rows below. |
| `src/zlog/ui/build.py` | ui | `win.log_header = LogHeaderBar(win.log_delegate, win.model)`; wrap `win.table` in a small container `QWidget`/`QVBoxLayout` (`[log_header, table]`, zero margins/spacing) and add *that* to `win._splitter` in place of `win.table` directly — the splitter's pane-0/pane-1 indices (`setStretchFactor`, `setSizes`) are index-based, not widget-identity-based, so this is a drop-in swap (confirmed no other file touches `win._splitter` directly). |
| `src/zlog/ui/main_window.py` | ui | Repaint the header (`win.log_header.update()`) alongside the existing triggers that already repaint the table for layout-affecting toggles: wrap, show-process, line-numbers, theme, font zoom/family/density, and window resize — same call sites, one extra line each, not new signal wiring. |
| `tests/test_log_header_bar.py` (new) | tests | Offscreen-Qt: labels present/positioned left-to-right in the expected order; a label is omitted when its underlying segment width is `0` (auto-hidden, or Process off); `sizeHint` height is stable across paint calls. |

## Architecture touch points

- **Threading:** none.
- **Model/proxy:** none — read-only mirror of the delegate's existing layout,
  no new column/filter.
- **Dependency direction:** unaffected — `LogHeaderBar` is `ui`-only, reaching
  into `LogItemDelegate`'s layout methods the same way `test_log_delegate.py`
  already does (same package, an accepted same-layer coupling in this
  codebase — not a new precedent).

## Risks & regressions to check

- **Must not drift from the delegate.** Both read `_col_widths` from the same
  delegate instance, so they can't disagree on width — but confirm the header's
  `QFontMetrics` is built from the *same* font as the table (`win.table.font()`),
  not a default one, or the two will compute different `cw`/glyph widths and
  visibly misalign.
- **Splitter restructure**: confirm `remember-splitter.md`'s saved sizes still
  restore sanely (they're pane sizes, unaffected by what's inside pane 0) and
  that the gutter/line-number column, which shifts everything right, is
  accounted for in the header the same way it is in the rows.
- **Merged multi-device tabs**: the header reflects one tab's shared layout,
  same as the rows already do — no per-source distinction needed here.
- Confirm the extra fixed-height widget doesn't visibly shift row alignment or
  eat into the log view's available height in a way that looks cramped at the
  app's minimum window size.

## Verification

- [x] `uv run pytest tests/test_log_header_bar.py` (6 passed) + a broader
      `-k "splitter or theme or font or zoom or density or process or wrap or
      main_window"` slice (196 passed) to catch splitter-restructure/repaint
      regressions
- [x] `uv run ruff check .` and `uv run ruff format --check .`
- [x] `run-zlog` screenshots: `populated` (plain), `line-numbers` (gutter
      shift), and a new `header-process-and-wrap` scenario — all pixel-aligned
      with the rows, including the Process column and the line-number gutter
- [x] Fixed one real bug found via screenshot: the "Lvl" label didn't fit the
      chip's 2-char-wide box and elided to "…" — shortened to "L" (matching
      that the real chip is one glyph wide, e.g. "I"/"W")

## Open questions

None — scope confirmed with the user: a label strip (not a tooltip), depends
on [auto-hide-empty-columns.md](auto-hide-empty-columns.md) so hidden segments
don't get a dangling label.
