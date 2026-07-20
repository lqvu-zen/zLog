# Plan: Inline search-match highlight

- **Status:** Done
- **Owner:** unassigned
- **Created:** 2026-07-15
- **Related:** [highlight-matches.md](highlight-matches.md), [match-navigation.md](match-navigation.md), backlog.md

## Goal

In Highlight mode, the matched *substring* inside a row's message lights up (not
just the whole-row tint), so it's obvious at a glance why a long line matched.

## Scope

- **In:** the message text only, in Highlight mode, for the current search term
  (substring or regex, honoring the Case toggle). A filled highlight rect is drawn
  behind each matched run before the message text is painted.
- **Out (non-goals):** Filter-mode inline highlight (every visible row matches
  there, so it's lower value — a follow-up if wanted); highlighting inside the tag
  column; multi-term / OR highlighting; regex named-group coloring.

## Design

| File | Layer | Change |
|---|---|---|
| `src/zlog/core/search.py` | core | `find_spans(text, term, regex, case) -> list[tuple[int, int]]` — reuses the same regex-compile / substring-find logic as `compile_matcher`, returning non-overlapping match spans instead of a bool. Pure, unit-tested (plain text, regex, case-insensitive, no match, empty term). |
| `src/zlog/ui/log_model.py` | ui | `set_highlight` additionally compiles a span-finder (`self._highlight_spans_fn`) alongside the existing bool matcher. New role `MATCH_SPANS_ROLE = HIGHLIGHT_ROLE + 1`; `data()` returns `find_spans(entry.message, ...)` for that role when the row matches the highlight predicate, else `[]`. |
| `src/zlog/ui/log_delegate.py` | ui | In `paint`, when `index.data(MATCH_SPANS_ROLE)` is non-empty: measure each span's pixel offset with `fm.horizontalAdvance` over the message prefix, and fill a small highlight rect behind each run before the existing single `drawText` call for the message (mirrors how `HIGHLIGHT_ROLE` already fills the row background). Works in both wrap and non-wrap paint paths. |
| `src/zlog/ui/theme.py` | ui | Add an `inline_match` token per `Theme` (a slightly stronger tint than `search_highlight`, since it sits on top of the row tint). |

## Architecture touch points

- **Model/proxy:** new read-only role on `LogTableModel`, computed per visible row
  in `data()` — no change to filtering, stays virtualized.
- **Colors** come from `ui/theme.py` (centralize-colors rule).
- No threading impact; no Qt in `core/search.py`.

## Risks & regressions to check

- Elided (non-wrap) rows: a span past the elided cutoff must not draw a rect past
  the visible text — clip the rect to the elided string's measured width.
- Regex with zero-width matches must not loop forever in `find_spans`.
- Turning Highlight mode off / clearing the term clears the spans (empty list).

## Verification

- [x] `uv run pytest` (`find_spans` cases; model returns spans only for matching rows in highlight mode)
- [x] `uv run ruff check .` and `uv run ruff format --check .`
- [x] Headless smoke: added `inline-match-highlight` and `inline-match-highlight-wrap`
      scenarios to the run-zlog driver; both screenshots show the matched substring
      highlighted within the row tint, including correctly across a wrapped line.

## Implementation note

Painting spans over word-wrapped text turned out to need `QTextLayout` (with
`FormatRange` background formats), not a manual `fm.horizontalAdvance` offset
calculation — that's the only Qt primitive that lays out wrapped text and
accepts per-character background formatting in one pass, so it reproduces
`drawText(Qt.TextWordWrap)`'s line breaks exactly. Non-wrap (elided) rows use
the same code path with an effectively unbounded line width, clipped to the
cell rect; an overlong matched line loses the "…" affordance in that rare case
(matched *and* longer than the cell) — accepted, documented in code.

## Open questions

- None blocking; Filter-mode inline highlight left as a documented non-goal.
