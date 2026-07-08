# Plan: Bookmarks / pinned lines

- **Status:** Done
- **Owner:** Vũ
- **Created:** 2026-07-08
- **Related:** detail-pane, copy-to-clipboard

## Goal

Mark interesting lines and jump between them (next/previous bookmark), so you can flag
events during a capture and navigate back to them.

## Scope

- **In:** toggle a bookmark on the selected row (Ctrl+B / context menu); a bookmark
  gutter marker or row indicator; **next/prev bookmark** navigation. Bookmarks are a
  set of row identities in the master list for the session.
- **Out:** persisting bookmarks across launches; naming/annotating bookmarks;
  bookmarks surviving Clear.

## Design

Bookmarks key off the master-list entry (stable while the log isn't cleared).

| File | Layer | Change |
|---|---|---|
| `src/zlog/ui/log_model.py` | ui | Model tracks a set of bookmarked source rows; `DecorationRole`/marker on column 0 (or a star glyph); toggle/clear methods; `dataChanged` on change. |
| `src/zlog/ui/main_window.py` | ui | Ctrl+B action + context-menu item to toggle on the selected row; next/prev-bookmark actions that select/scroll via the proxy; clears with the log. |

## Architecture touch points

- Model stays virtualized; bookmark state is a small set keyed by source row index.
  Clearing the log clears bookmarks (row indices are no longer valid).
- No core change. Colors/markers via theme where a color is needed.
- Versioning: no bump.

## Risks & regressions to check

- Toggling maps proxy selection → source row correctly under active filters.
- Bookmarked row hidden by a filter: next/prev skips it or surfaces it (decide + test).
- Clear resets bookmarks; no stale indices.

## Verification

- [ ] `uv run pytest` (headless: toggle, next/prev selection, clear resets)
- [ ] `uv run ruff check .` and `uv run ruff format --check .`
