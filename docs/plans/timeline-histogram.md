# Plan: Timeline histogram

- **Status:** Draft  <!-- Draft | Approved | In progress | Done | Abandoned -->
- **Owner:** unassigned
- **Created:** 2026-07-20
- **Related:** [scrollbar-heat.md](scrollbar-heat.md), [error-sparkline.md](error-sparkline.md), [goto-line-time.md](goto-line-time.md)

## Goal

A thin horizontal band above the log that charts log volume (and error density)
over the capture's time span, so you can see bursts/quiet periods at a glance and
click a spot to jump the view to that moment.

## Scope

- **In:** a compact histogram widget bucketing entries by time; bar height =
  volume, an error-tint overlay = share of W/E/F; click-to-seek scrolls the log to
  the first row in that bucket; a View toggle (persisted), hidden by default;
  debounced rebuild as rows stream in.
- **Out (non-goals):** zoom/pan into a sub-range, selection-to-filter (that's a
  future time-range integration — the `since:`/`until:` tokens already exist),
  per-tag series, live animation. One static band that reflects the current model.

## Design

The bucketing is pure and Qt-free (a list of counts over N time buckets), mirroring
how `core/heat.py` and `core/sparkline.py` already reduce the model to a small
drawable summary. The widget is a thin `QWidget` that paints the buckets and maps a
click x back to a source row, reusing the same map-to-proxy + scrollTo path as
bookmarks/goto.

| File | Layer | Change |
|---|---|---|
| `src/zlog/core/histogram.py` (new) | core | `bucketize(times: list[datetime \| None], levels: list[str], buckets: int) -> list[Bucket]` where `Bucket` is `(count, error_count, first_index)`. Spans min→max parseable time into `buckets` equal slots; unparneable-time rows fold into the previous slot; empty input → `[]`. Also `bucket_for_index(...)`/`index_for_x(...)` helpers as needed. Pure, unit-tested. |
| `src/zlog/ui/histogram_bar.py` (new) | ui | `HistogramBar(QWidget)`: fixed ~28px height. `set_data(buckets)` stores + `update()`. `paintEvent` draws one vertical bar per bucket (height ∝ count, an error-tinted sub-bar ∝ error_count), theme colors from `ui/theme.py` tokens. `mousePressEvent` → emit `seek_requested(first_index)` for the clicked bucket. No model knowledge. |
| `src/zlog/ui/main_window.py` | ui | Build `self.histogram_bar`, insert in `_build_layout` between the chip bar and the splitter. A debounced rebuild (reuse the existing `_schedule_heat`/counts debounce pattern — a single-shot timer, ~200ms) reads `model.all_entries()` → parse times (reuse `timefmt.parse_logcat_time`) → `bucketize(...)` → `histogram_bar.set_data(...)`. `seek_requested(src)` → map to proxy row, `selectRow` + `scrollTo` (same as `_jump_to_bookmark_item`). A View toggle action shows/hides the bar, persisted in settings (`show_histogram`, default False). Rebuild on rows-inserted / filter-change / clear, debounced. |
| `src/zlog/core/settings.py` | core | Add `"show_histogram": False` to DEFAULTS. |
| `tests/test_histogram.py` (new) | — | `bucketize`: even split across N buckets; error_count counts only W/E/F; first_index points at the first row in each bucket; unparseable-time handling; empty input. |

## Architecture touch points

- **Threading:** none — bucketing runs on the main thread but is debounced and
  O(rows) over a bounded (ring-capped) model; same cost class as the sparkline/heat
  rebuilds that already run there.
- **Model/proxy:** read-only (`all_entries()`); no new column or filter gate.
  Click-seek uses the existing proxy map + `scrollTo`.
- **Dependency direction:** `core/histogram.py` is Qt-free; `ui/histogram_bar.py`
  imports only Qt + theme tokens; wiring in `main_window`. `ui → core` holds.

## Risks & regressions to check

- Perf: rebuilding on every batch would be O(rows) per batch → debounce to one pass
  per burst (like counts/heat). Verify a fast dump doesn't stutter.
- Time parsing: many rows share a timestamp; a capture with no parseable times (odd
  formats) must degrade to volume-only or hide gracefully, not divide-by-zero.
- Click mapping when filtered: a bucket's `first_index` may be hidden by the current
  filter → seek to the nearest visible row (or no-op with a status hint), like the
  bookmark-jump behavior.
- Layout: the band adds vertical furniture — hidden by default, toggled from View;
  keep it thin so it doesn't crowd the log.

## Verification

- [ ] `uv run pytest` (new `test_histogram.py`; wiring covered by a main-window smoke)
- [ ] `uv run ruff check .` and `uv run ruff format --check .`
- [ ] `run-zlog` scenario `timeline-histogram`: seed timed rows, show the bar,
      screenshot; assert a click seeks the view.

## Open questions

- Bucket count: fixed (e.g. 120) or width-derived (one bar per ~4px)? Leaning
  width-derived so bars stay legible on resize (recompute on the `resized` signal).
- Error overlay vs. a separate error line — leaning an error-tinted sub-bar within
  each volume bar (one pass, one row of pixels).
