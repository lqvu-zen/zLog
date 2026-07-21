# Plan: Regex named-group extraction → columns

- **Status:** Done  <!-- Draft | Approved | In progress | Done | Abandoned -->
- **Owner:** unassigned
- **Created:** 2026-07-20
- **Related:** [logcat-style-ui.md](logcat-style-ui.md), [fixed-columns-middle-elide.md](fixed-columns-middle-elide.md), [tag-summary.md](tag-summary.md)

## Goal

Let the user supply a regex with named groups (e.g.
`latency=(?P<ms>\d+)ms .* url=(?P<url>\S+)`); each named group becomes an ad-hoc
field extracted from every matching line, surfaced as sortable extra columns —
turning free-text logs into structured, filterable data.

## Scope

- **In:** a manager dialog to enter/save one or more named-group patterns; a pure
  extractor that maps an entry's message → `{group: value}`; the values exposed via
  a model role; a way to *see* them (see the "Open question: how to display"
  below — the current single-line delegate has no column model). Patterns persisted.
- **Out (non-goals):** multi-line/whole-entry regex, type coercion beyond string,
  computed columns, joining across lines. Extraction is per-line, string-valued.

## Design

Extraction is pure and testable; the hard part is *presentation*, because the
Android-Studio redesign replaced the multi-column table with a single-line paint
delegate (`fixed-columns-middle-elide.md`). This plan keeps extraction Qt-free and
proposes the lightest presentation that fits that delegate.

| File | Layer | Change |
|---|---|---|
| `src/zlog/core/extract.py` (new) | core | `compile_extractors(patterns: list[str]) -> list[Pattern]` (skip invalid, like the query regex path); `extract(entry_message, patterns) -> dict[str, str]` returning the union of named-group matches (first match wins per group). Pure, unit-tested. |
| `src/zlog/ui/log_model.py` | ui | Hold compiled extractors (`set_extractors(patterns)`); a new `EXTRACT_ROLE` returns the `{group: value}` dict for a row (computed lazily, not stored). Keep the model virtualized — no per-row widgets. |
| `src/zlog/ui/extract_dialog.py` (new) | ui | Small manager: list of patterns, add/edit/remove, invalid-regex feedback; returns the pattern list. |
| `src/zlog/ui/main_window.py` | ui | View → "Extract fields…" opens the dialog; apply → `model.set_extractors(...)`, persist `extract_patterns` in settings. Presentation (see open question) — the recommended first cut: **append the extracted `key=value` pairs to the detail pane** and offer **View → Extracted Fields Summary** (a Tag-Summary-style table of group values by count, double-click to filter via a generated query). This delivers the value without reintroducing a column model. A later phase can add inline mini-columns if warranted. |
| `src/zlog/core/settings.py` | core | Add `"extract_patterns": []` to DEFAULTS. |
| `tests/test_extract.py` (new) | — | `extract`: single/multiple groups, non-match → empty, invalid pattern skipped, first-match-wins; `compile_extractors` drops bad patterns. |

## Architecture touch points

- **Threading:** none; extraction is per-visible-row (lazy via the role) or batched
  in the summary pass.
- **Model/proxy:** a new read role; no filter change in phase 1 (the summary dialog
  generates a normal query to filter). If inline columns land later, that's a
  delegate change, not a proxy change.
- **Dependency direction:** `core/extract.py` Qt-free; model/dialog in `ui`.

## Risks & regressions to check

- Perf: compiling once (not per row) and extracting only for visible rows / the
  summary pass keeps it O(visible). A catastrophic-backtracking pattern could stall
  — cap with a simple guard or document the risk.
- The delegate rethink is the real cost; phase 1 deliberately avoids it by routing
  extracted data to the detail pane + a summary dialog. Confirm that's acceptable
  before investing in inline columns.
- Invalid regex must degrade (skip that pattern, tint/notify), never crash.

## Verification

- [ ] `uv run pytest` (new `test_extract.py`; model role smoke)
- [ ] `uv run ruff check .` and `uv run ruff format --check .`
- [ ] `run-zlog` scenario `regex-extract`: apply a pattern, screenshot the summary.

## Open questions

- **How to display extracted fields** (the crux): (a) detail pane + summary dialog
  only — smallest, fits the current delegate; (b) inline mini-columns in the
  delegate — richest but reopens the retired column model; (c) a dedicated
  side-panel table. Leaning (a) for a first release, revisit (b) with usage.
- Whether patterns are global or per-session (leaning global/persisted, like
  highlight rules).
