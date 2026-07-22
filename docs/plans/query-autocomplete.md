# Plan: Context-aware query-bar autocomplete

- **Status:** Done  <!-- Draft | Approved | In progress | Done | Abandoned -->
- **Owner:** unassigned
- **Created:** 2026-07-22
- **Related:** [query-token-highlight.md](query-token-highlight.md), [filter-chips.md](filter-chips.md), [min-level-selector.md](min-level-selector.md), [search-history.md](search-history.md)

## Goal

As you type in the query bar, show an Android-Studio-style completion popup for the
**current token**: field keys (`level:`, `tag:`, `pid:`, `proc:`, `package:`,
`since:`, `until:`, `device:`, `-`) when starting a token, level names with a
"Filter by ‹LEVEL› or higher" hint after `level:`, and live **tag / PID / process**
values from the current log after `tag:` / `pid:` / `proc:`/`package:`. Each row
shows a right-aligned dim description. Enter/Tab inserts the highlighted item,
replacing just the token being typed.

## Scope

- **In:** a pure completion "brain" (current-token detection + context → ordered
  suggestions with descriptions); a popup on the query bar with a description
  column; token-scoped replacement on accept; live tag/pid/proc values fed from
  the model (capped). Works alongside the existing token tinting.
- **Out (non-goals):** fuzzy ranking, value completion for `since:`/`until:` (times),
  multi-token snippets, learning from history for field values. The existing
  whole-line **search-history** completer is replaced by this token completer (bare
  words still get history suggestions — see Design).

## Design

The current-token logic and suggestion set are **pure** (`core.completion`), so they
unit-test without Qt. The widget side is a `QCompleter` whose *completion prefix* is
the current token's value part (not the whole line); on activation the window swaps
that token span for the chosen value using the existing `token_spans` machinery. The
description column is a small item delegate painting `Qt.UserRole+1` right-aligned in
the muted color (like the query token-highlight palette).

| File | Layer | Change |
|---|---|---|
| `src/zlog/core/completion.py` (new) | core | `Suggestion = (value, description)`. `current_token(text, cursor) -> (start, end, token_str)` (whitespace/quote-aware, reuse the `token_spans` scanner). `completions(text, cursor, *, tags, procs, pids) -> (start, end, prefix, list[Suggestion])`: classify the token (`level:`→level names+desc; `tag:`→tags; `pid:`→pids; `proc:`/`package:`→procs; bare/`-`→field keys+desc), filtering the candidate list by the typed prefix (case-insensitive). Pure, unit-tested. Level metadata (V/D/I/W/E/F full names + "or higher" text) lives here. |
| `src/zlog/ui/completion_popup.py` (new) | ui | `SuggestionDelegate(QStyledItemDelegate)` painting the display text left + the description (a data role) right in `muted`. A tiny helper to build a `QStandardItemModel` from `list[Suggestion]`. |
| `src/zlog/ui/query_line_edit.py` | ui | Own a `QCompleter` (popup uses `SuggestionDelegate`, `caseInsensitive`, `UnfilteredPopupCompletion` since we filter ourselves). On `textEdited`/cursor move, ask the window (via a callback/signal) for `completions(...)`, load the model, set the completion prefix, and `complete()` anchored under the caret (or hide when empty). On `activated(text)`, replace the current token span with the value + a trailing space; keep the caret after it. Expose a `set_context_provider(fn)` the window sets. Keep the paintEvent token tinting. |
| `src/zlog/ui/main_window.py` | ui | Provide the live candidate lists to the query bar: `tags` (from `tag_counts` keys / a model accessor), `procs` (`model.process_names()`), `pids` (`model.pid_names().keys()` — add a small accessor), each capped (e.g. 300, most-frequent/most-recent first). Refresh them debounced on model change (reuse a timer). Replace the whole-line history `QCompleter` wiring with the context completer; feed bare-word context from `search_history` so typing a plain word still suggests recent searches. |
| `tests/test_completion.py` (new) | — | `current_token` at various cursor positions incl. quoted tokens; `completions` for level (values + descriptions, prefix filter), tag/pid/proc (from supplied lists), bare token → field keys, `-` prefix, empty text → keys. |

## Architecture touch points

- **Threading:** none. Building suggestions is O(candidates) on the main thread,
  debounced; candidate lists are capped so the popup stays snappy on huge captures.
- **Model/proxy:** read-only accessors for tags/procs/pids; no new column or gate.
- **Dependency direction:** `core.completion` is Qt-free; `ui.query_line_edit` /
  `ui.completion_popup` are Qt; the window supplies live values. `ui → core` holds.

## Risks & regressions to check

- Token-scoped replacement: inserting must replace only the current token, not the
  whole line (the default `QCompleter` replaces everything) — hence the manual
  span swap on `activated`.
- The completer popup must not fight the token tinting repaint or the debounced
  `_apply_query`; ensure `complete()`/hide don't trigger a filter apply loop.
- Programmatic `setText`/`_set_query_text` (presets, isolate, level sync) must not
  pop the completer (only user edits should) — gate on `textEdited`, not
  `textChanged`.
- Live lists on a huge log: cap + debounce so `tags`/`pids` don't rebuild per batch.
- Case-insensitive prefix match; quoted values (`tag:"My Tag"`) stay one token.
- Losing the history completer shouldn't remove recent-search help for bare words —
  fold history into the bare-token suggestions.
- Enter behavior: when the popup is open, Enter accepts the suggestion; when closed,
  Enter applies the filter (don't break the existing submit).

## Verification

- [ ] `uv run pytest` (new `test_completion.py`; a query-bar smoke: typing `level:`
      loads level suggestions; `tag:` loads supplied tags; accepting replaces the token)
- [ ] `uv run ruff check .` and `uv run ruff format --check .`
- [ ] `run-zlog` scenario: type `level:` and screenshot the popup with descriptions.

## Open questions

- Trigger: pop on every keystroke in a token vs. only after a `:` / min 1 char.
  Leaning: show once the token has ≥1 char, and immediately after a field `:`.
- Ordering of live values: by frequency (needs counts) vs. alphabetical. Leaning
  frequency for tags (we have `tag_counts`), alphabetical for procs/pids.
- Show the field-key list on an empty query (caret in empty bar) too? Leaning yes —
  it advertises the syntax.
