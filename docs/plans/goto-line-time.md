# Plan: Go to timestamp / line

- **Status:** Draft
- **Owner:** unassigned
- **Created:** 2026-07-15
- **Related:** [match-navigation.md](match-navigation.md), [relative-time-column.md](relative-time-column.md), backlog.md

## Goal

`Ctrl+G` opens a quick input; typing a line number or a time jumps the selection
and scroll position straight to that row, without hunting by eye or search.

## Scope

- **In:** one input box. A value of all digits is a 1-based line number (into the
  currently visible/filtered rows, matching what the user counts on screen). A
  value containing `:` is a time-of-day (`HH:MM:SS` or `HH:MM:SS.mmm`, optionally
  prefixed `MM-DD `); jumps to the first visible row at or after that time.
- **Out (non-goals):** a persistent/dockable navigation panel; jumping into rows
  hidden by the current filter (out of scope — the user filters first, then jumps
  within what's visible, same model as match-navigation); reverse (time-to-line) lookup UI.

## Design

| File | Layer | Change |
|---|---|---|
| `src/zlog/core/timefmt.py` | core | `parse_time_of_day(s) -> time \| None` — parses `HH:MM:SS[.mmm]`, tolerant of a leading `MM-DD ` (discarded; comparison is time-of-day only, consistent with the module's documented single-day-capture assumption). |
| `src/zlog/core/timefmt.py` | core | `first_at_or_after(times: list[str], target: time) -> int \| None` — pure scan over already-parsed `entry.time` strings (via `parse_logcat_time`), returns the index of the first row at/after `target`, or `None` if every row is before it (caller then jumps to the last row). Unit-tested. |
| `src/zlog/ui/main_window.py` | ui | `QShortcut("Ctrl+G")` → `_open_goto()`: `QInputDialog.getText` with placeholder `"Line number, or time HH:MM:SS"`. All-digit input → clamp to `[1, proxy.rowCount()]`, select that visible row (1-based). Otherwise parse as time via `parse_time_of_day`; on success, walk visible proxy rows' `entry.time` with `first_at_or_after` and select/scroll (reuses the same select+`scrollTo` helper `_goto_match` already uses). Invalid input shows a status-bar message and does nothing. |

## Architecture touch points

- Read-only over the proxy's visible rows on the main thread, same shape as
  `match-navigation`'s `_matching_proxy_rows` — O(visible) per jump, fine.
- No model/proxy change (no new filter predicate); `core/timefmt.py` stays Qt-free.

## Risks & regressions to check

- Empty proxy (no rows, or everything filtered out): dialog is a no-op with a
  status message, not a crash.
- Line number beyond the visible count clamps to the last row rather than erroring.
- A time before every visible row's time selects the first row; after every row
  selects the last (documented, not an error).

## Verification

- [ ] `uv run pytest` (`parse_time_of_day` + `first_at_or_after` edge cases: no
      match, exact match, out-of-range, malformed input)
- [ ] `uv run ruff check .` and `uv run ruff format --check .`
- [ ] Manual: Ctrl+G, type a line number and a time, confirm selection + scroll.

## Open questions

- None blocking.
