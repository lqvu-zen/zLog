# Plan: Match navigation (next / previous)

- **Status:** Done
- **Owner:** Vũ
- **Created:** 2026-07-08
- **Related:** highlight-matches (flagged this as its follow-up), regex-search

## Goal

Step between search matches (buttons + F3 / Shift+F3) with a "3 / 12" counter — most
useful in Highlight mode where matches are interspersed with non-matching lines.

## Scope

- **In:** ◄ / ► buttons and a match counter near the search box; F3 / Shift+F3
  shortcuts; each step selects and scrolls to the next/previous visible row whose
  `tag + message` matches the search term, wrapping around.
- **Out:** cross-filter search; persisting match position; regex capture highlighting
  within a line.

## Design

Matching reuses the compiled search matcher over the proxy's visible rows.

| File | Layer | Change |
|---|---|---|
| `src/zlog/ui/main_window.py` | ui | Add `match_prev_btn`/`match_next_btn` + `match_label`; `_matching_proxy_rows()` returns the visible rows matching the current term; `_goto_match(step)` moves selection/scroll and updates the label; recompute the count when search/mode/data change. |

## Architecture touch points

- Read-only over the proxy on the main thread; model stays virtualized. Iterating
  visible rows is O(visible) per navigation — fine.
- No core change; reuses `core.search.compile_matcher`.
- Versioning: no bump.

## Risks & regressions to check

- Empty term → counter hidden/"0", buttons no-op.
- Works in both Filter mode (every visible row matches) and Highlight mode.
- Count updates as new batches stream in (recompute on rowsInserted, cheaply).

## Verification

- [ ] `uv run pytest` (headless: `_matching_proxy_rows` + `_goto_match` selection)
- [ ] `uv run ruff check .` and `uv run ruff format --check .`
- [ ] Headless: seed mixed rows in highlight mode, step next/prev, assert selection
