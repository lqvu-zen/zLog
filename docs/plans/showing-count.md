# Plan: "Showing X of Y" filtered count

- **Status:** Draft
- **Owner:** Vũ
- **Created:** 2026-07-08
- **Related:** level-counts

## Goal

When a filter is active, the status bar shows how many rows are visible vs. total
(e.g. "Showing 240 of 12,003 lines"), so it's obvious the view is filtered.

## Scope

- **In:** extend the existing count label: when `proxy.rowCount() < model.rowCount()`
  show "Showing X of Y lines"; otherwise the current "Y lines". Thousands separators.
- **Out:** per-filter breakdowns; a separate widget.

## Design

Pure presentation off counts already available.

| File | Layer | Change |
|---|---|---|
| `src/zlog/ui/main_window.py` | ui | `_update_counts` compares `proxy.rowCount()` to `model.rowCount()` and formats accordingly; also refresh on proxy row changes (filters), not just model inserts. |

## Architecture touch points

- Reads counts on the main thread; no model/proxy change. Level tally (if present)
  stays appended.
- Versioning: no bump.

## Risks & regressions to check

- Count updates when filters change (connect to proxy layoutChanged/rowsRemoved), not
  only on new data.
- No filter → shows plain total (no "Showing … of …").

## Verification

- [ ] `uv run pytest` (headless: label text with and without a filter)
- [ ] `uv run ruff check .` and `uv run ruff format --check .`
