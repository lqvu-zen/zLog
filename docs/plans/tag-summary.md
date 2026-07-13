# Plan: Tag summary (histogram) dialog

- **Status:** Done
- **Owner:** unassigned
- **Created:** 2026-07-11
- **Related:** ROADMAP v1.4 "Reading & analysis" (tag/level histogram),
  [level-counts.md](level-counts.md), [tag-highlight.md](tag-highlight.md)

## Goal

After this ships, View → **Tag Summary** opens a dialog listing the tags in the
current view by line count (noisiest first). Double-clicking a tag filters the log
to it — so you can see which tags dominate and jump to one.

## Scope

- **In:** pure `tag_counts(entries)`; a View → Tag Summary dialog (tag + count
  table over the visible rows); double-click a row to set `tag:<tag>` in the query.
- **Out:** a live docked panel, per-level breakdown per tag, charts, right-click
  actions in the dialog.

## Design

| File | Layer | Change |
|---|---|---|
| `src/zlog/core/summary.py` | core | `tag_counts(entries) -> list[tuple[str, int]]` — count entries with a non-empty tag, sorted by count desc then tag asc. Pure. |
| `src/zlog/ui/main_window.py` | ui | Import `tag_counts` + `QDialog`/`QTableWidget`/`QTableWidgetItem`/`QAbstractItemView`. View → **Tag Summary…**. `_show_tag_summary()` builds a modal dialog with a read-only tag/count table from `_filtered_entries()`; `cellDoubleClicked` sets the query to `tag:<tag>` and closes. |
| `tests/test_summary.py` | tests | `tag_counts` ordering, tie-break, and that empty-tag (banner) lines are ignored. |

## Architecture touch points

- **core stays Qt-free / tested;** the dialog is thin view code over the pure count.
- **Operates on visible rows** (`_filtered_entries`), so the summary reflects the
  active filter.

## Risks & regressions to check

- **Large logs:** one `Counter` pass when the dialog opens (O(visible)); fine.
- **Empty view:** dialog opens with an empty table, no crash.
- **Double-click filter:** setting `tag:<tag>` runs through the normal query path.

## Verification

- [ ] `uv run pytest`
- [ ] `uv run ruff check .` and `uv run ruff format --check .`
- [ ] Manual: open Tag Summary on a capture; double-click filters to that tag.
