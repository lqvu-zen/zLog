# Plan: Filter chips

- **Status:** Done  <!-- Draft | Approved | In progress | Done | Abandoned -->
- **Owner:** Claude
- **Created:** 2026-07-18
- **Related:** query-token-highlight.md, exclude-pid-proc.md, clear-filters-button.md

## Goal

Render the active query bar's tokens (`level:E`, `tag:Foo`, `proc:com.x`,
`-noise`, `/re/`, plain words) as a row of removable chips just under the query
bar; clicking a chip's × drops that token and re-applies the filter — quick
editing without hand-parsing the query text.

## Scope

- **In:** a chip bar reflecting the current query; per-chip remove; hidden when
  the query is empty. Chips are read-only labels + an × (no inline editing).
- **Out (non-goals):** adding tokens via chips, drag-reorder, editing a chip's
  value in place (removing then retyping covers it).

## Design

`core/query.py` already exposes `token_spans(text) -> [(start, end, kind)]`, a
quote-aware tokenizer that also classifies each token — exactly the data a chip
row needs, and already unit-tested. The chip bar is a pure view driven by those
spans; removing a chip slices its `(start, end)` out of the query text.

| File | Layer | Change |
|---|---|---|
| `src/zlog/core/query.py` | core | Add `remove_span(text, start, end) -> str`: return `text` with `[start,end)` removed and surrounding whitespace collapsed to a single space, trimmed. Pure + unit-tested (removing token N leaves the rest parseable and equal to the same query minus that token). |
| `src/zlog/ui/filter_chips.py` | ui | New `FilterChipBar(QWidget)`. `set_query(text)`: clear, then for each `token_spans(text)` add a chip (a small framed `QLabel`-like widget: kind-tinted text + an × button). Each chip's × emits `remove_requested(start, end)`. A `QHBoxLayout` with a trailing stretch; the widget hides itself when there are no tokens. Kind→color reuses the same palette family as the query-bar token highlight. |
| `src/zlog/ui/main_window.py` | ui | Build `self.chip_bar = FilterChipBar()`, insert it in `_build_layout` between `filter_row` and the splitter. On `self.query.textChanged` (already connected to `_schedule_query_apply`) also call `self.chip_bar.set_query(text)` — add a direct connection so chips track every edit. `chip_bar.remove_requested` → `_remove_query_span(start, end)`: `self._set_query_text(remove_span(self.query.text(), start, end))` (which re-applies via `_apply_query`). |

Removing by character span (not by key) is deliberate: it handles duplicate
tokens (`-a -b`) and repeated excludes correctly, where `_remove_query_token`
(key-based) would drop both.

## Architecture touch points

- **Threading:** none.
- **Model/proxy:** none — the chip bar only rewrites the query text, which flows
  through the existing `_apply_query` path.
- **Dependency direction:** `ui.filter_chips` imports `core.query`; one-way. The
  chip bar knows nothing about the model.

## Risks & regressions to check

- Span validity: `set_query` runs on the *current* text and `remove_span` uses
  spans from that same text, so an edit between display and click can't desync as
  long as chips are rebuilt on every `textChanged` (they are).
- Programmatic query changes (`_set_query_text`, isolate, presets) fire
  `textChanged`, so chips stay in sync — verify isolate/preset apply repaints
  chips.
- Empty/whitespace query → no chips, bar hidden (no stray empty row).
- Quoted values (`tag:"two words"`) stay one chip — `token_spans` is quote-aware.

## Verification

- [ ] `uv run pytest` (unit-test `remove_span` for first/middle/last token and
      quoted tokens; assert the remaining query parses to the same `QuerySpec`
      minus the removed part).
- [ ] `uv run ruff check .` and `uv run ruff format --check .`
- [ ] `run-zlog` driver scenario `filter-chips`: set a multi-token query,
      screenshot the chip row.

## Open questions

- Placement above vs. below the query bar. Decision: below, so chips read as a
  breakdown of the bar directly over them; revisit if it crowds the layout.
