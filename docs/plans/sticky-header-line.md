# Plan: Sticky header line

- **Status:** Draft  <!-- Draft | Approved | In progress | Done | Abandoned -->
- **Owner:** unassigned
- **Created:** 2026-07-20
- **Related:** [detail-pane.md](detail-pane.md), [bookmark-labels.md](bookmark-labels.md), [stack-trace-folding.md](stack-trace-folding.md)

## Goal

Keep an anchor line (the selected line, or the nearest bookmark above the
viewport) pinned as a thin strip at the top of the log while you scroll, so you
never lose track of which entry you're investigating as its context scrolls away.

## Scope

- **In:** a one-line sticky strip overlaid at the top of the log viewport showing
  the current anchor entry (rendered like a log row); updates as you scroll;
  clicking it scrolls back to that row; a View toggle (persisted), off by default.
- **Out (non-goals):** multiple stacked sticky lines, sticky *sections* (à la code
  folding headers), sticky while wrap re-fits mid-stream. One anchor line.

## Design

Anchor = the selected source row if it's above the current viewport top; otherwise
the nearest bookmark above the top; otherwise nothing (strip hidden). The strip is
a separate 1-row widget painted with the *same* `LogItemDelegate` so it looks
identical to a real row, positioned over the table viewport's top edge.

| File | Layer | Change |
|---|---|---|
| `src/zlog/ui/sticky_header.py` (new) | ui | `StickyHeader(QWidget)` overlaying the table viewport top. `set_entry(index)` stores a proxy index (or None → hide) and `update()`. `paintEvent` builds a `QStyleOptionViewItem` sized to the row and calls `self._delegate.paint(...)` so it matches the log exactly. `mousePressEvent` → emit `clicked(source_row)`. Fixed one-line height (`fm.height()+4`). |
| `src/zlog/ui/main_window.py` | ui | Own a `StickyHeader` parented to `self.table.viewport()`, sharing `self.log_delegate`. On `table.verticalScrollBar().valueChanged` (debounced with the existing wrap/heat timers or a light throttle) compute the anchor: `first_visible = table.rowAt(0)`; if the selected row's proxy row `< first_visible`, anchor = selected; else nearest bookmark proxy-row `< first_visible`; else None. `set_entry(anchor)` + reposition to viewport top. `clicked(src)` → `scrollTo`/`selectRow` (reuse `_jump_to_bookmark_item`'s body). Reposition on `table.resized`. A View toggle action + `show_sticky_header` setting gate it. |
| `src/zlog/core/settings.py` | core | Add `"show_sticky_header": False` to DEFAULTS. |
| `tests/test_main_window_settings.py` | — | Smoke: with the toggle on and a selected row scrolled out of view, `sticky_header` has an entry set; scrolling back clears it; clicking emits/does the jump. (Anchor-selection logic is the testable core — consider extracting `pick_anchor(first_visible, selected_row, bookmark_rows) -> int \| None` into `core` for a pure unit test.) |

## Architecture touch points

- **Threading:** none.
- **Model/proxy:** read-only; the strip renders one existing index via the shared
  delegate. No new roles.
- **Dependency direction:** the widget imports the delegate (both `ui`); anchor
  math (if extracted) is Qt-free in `core`. `ui → core` holds.

## Risks & regressions to check

- Overlap/geometry: the strip must sit exactly over the first visible row's top and
  resize with the viewport (`resizeEvent`/`resized`); it must not eat clicks meant
  for the row beneath except its own.
- Wrap mode: rows are variable height; anchor height uses one line (the metadata
  band), consistent with how wrap paints the first line — verify it reads cleanly.
- Perf: recompute the anchor on scroll must be O(1)-ish (just `rowAt` + a couple of
  comparisons), throttled so fast scrolling stays smooth.
- Selection vs. bookmark precedence and the "nothing to anchor" case (hide, no
  flicker).

## Verification

- [ ] `uv run pytest` (pure `pick_anchor` if extracted; main-window smoke)
- [ ] `uv run ruff check .` and `uv run ruff format --check .`
- [ ] `run-zlog` scenario `sticky-header`: select a row, scroll down, screenshot the
      pinned strip.

## Open questions

- Anchor priority: selected-line-first vs. bookmark-first. Leaning selected line
  first (it's the thing you're actively looking at), bookmark as fallback.
- Whether to also pin when *no* selection but scrolled far — probably not; keep it
  intentional (only when there's a chosen anchor).
