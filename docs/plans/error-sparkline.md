# Plan: Error-rate sparkline in the status bar

- **Status:** Done
- **Owner:** unassigned
- **Created:** 2026-07-11
- **Related:** ROADMAP v1.4 "Reading & analysis", [level-counts.md](level-counts.md),
  [scrollbar-heat.md](scrollbar-heat.md)

## Goal

After this ships, the status bar shows a tiny block-character sparkline of
error/fatal density over the recent tail of the log, so a spike in errors is
visible at a glance next to the level counts.

## Scope

- **In:** pure sparkline rendering + error bucketing; a status-bar label updated
  with the level counts, over the last ~500 source lines in ~20 buckets.
- **Out:** time-axis bucketing (uses line position, not wall-clock), per-tag
  sparklines, click interaction, a full chart.

## Design

| File | Layer | Change |
|---|---|---|
| `src/zlog/core/sparkline.py` | core | `sparkline(values)` maps ints to `▁▂▃▄▅▆▇█` scaled to the max (empty→""; all-zero→flat baseline). `error_rate_sparkline(ranks, error_rank, buckets=20)` counts error-or-above per bucket and renders. Pure. |
| `src/zlog/ui/main_window.py` | ui | A `spark_label` permanent status-bar widget (tooltip "Error rate over the last 500 lines"). In `_update_counts`, feed the ranks of the last 500 source rows to `error_rate_sparkline` and set the label. |
| `tests/test_sparkline.py` | tests | Scaling (max→full block, empty→"", all-zero→baseline) and error bucketing (errors concentrated in the second half tower there). |

## Architecture touch points

- **Pure/tested rendering** in core; the UI only slices the last N ranks and sets a
  label — reuses the existing `_update_counts` trigger (rows changed).
- **Bounded work:** at most ~500 `entry_at` reads per update; no full-list copy.

## Risks & regressions to check

- **Empty / no-error log:** empty string / flat baseline, no crash.
- **Unicode width:** block chars are single-width; fine in a status label.
- **Update cost:** ~500 reads on each counts update (already throttled by batching).

## Verification

- [ ] `uv run pytest`
- [ ] `uv run ruff check .` and `uv run ruff format --check .`
- [ ] Manual: stream a log with error bursts; the sparkline rises during bursts.
