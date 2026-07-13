# Plan: Scrollbar heat marks (error minimap)

- **Status:** Done
- **Owner:** unassigned
- **Created:** 2026-07-11
- **Related:** ROADMAP v1.4 "Reading & analysis", [severity-navigation.md](severity-navigation.md)

## Goal

After this ships, the log's vertical scrollbar shows small red ticks at the
positions of error/fatal lines — a minimap so you can see, and scroll to, where
problems cluster in a long capture.

## Scope

- **In:** a custom scrollbar that paints error/fatal position marks; marks are
  recomputed (debounced) over the visible rows and bucketed so their count stays
  bounded regardless of log size; color from the active theme.
- **Out:** warning marks, bookmark/search marks on the bar, click-to-jump on a
  mark (severity nav already covers jumping), hover tooltips.

## Design

| File | Layer | Change |
|---|---|---|
| `src/zlog/core/heat.py` | core | `heat_marks(ranks, n, error_rank, buckets=200) -> list[float]` — bucket each error-or-above row into one of `buckets` slots; return sorted unique slot fractions (0..1). Pure; caps the mark count at `buckets`. |
| `src/zlog/ui/heat_scrollbar.py` | ui | `HeatScrollBar(QScrollBar)` with `set_marks(fractions, color)`; `paintEvent` draws the native bar then thin ticks at `frac * height`. |
| `src/zlog/ui/main_window.py` | ui | Install a `HeatScrollBar` as the table's vertical scrollbar. A single-shot debounce `QTimer` (400 ms) recomputes on proxy rows-inserted/removed/reset/layout-changed and on theme change. `_recompute_heat()` feeds `heat_marks((self._proxy_rank(r) for r in range(n)), n, LEVEL_RANK["E"])` and the theme's error color to the bar. |
| `tests/test_heat.py` | tests | Bucketing: errors at the ends map to ~0.0 and ~1.0; count never exceeds `buckets`; empty input → no marks. |

## Architecture touch points

- **Pure/tested bucketing** in core; the widget only paints; the window wires the
  debounce. Passing a generator (not a list) avoids materializing ranks for huge logs.
- **Debounced:** recompute runs ~400 ms after activity settles, not per batch, so a
  fast stream doesn't thrash it.

## Risks & regressions to check

- **Perf:** one O(visible) pass per settle; the generator + `buckets` cap keep memory
  and mark count bounded.
- **Filtered view:** marks are computed over proxy (visible) rows, so positions match
  what's shown.
- **Empty / no-error view:** no marks, no crash.
- **Scrollbar replacement:** set the custom bar after the view exists; normal
  scrolling still works (we only add paint on top).

## Verification

- [ ] `uv run pytest` (core bucketing)
- [ ] `uv run ruff check .` and `uv run ruff format --check .`
- [ ] Manual: a capture with scattered errors shows red ticks down the scrollbar.
