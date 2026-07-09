# Plan: Search history

- **Status:** Done
- **Owner:** Vũ
- **Created:** 2026-07-08
- **Related:** regex-search, filter-presets

## Goal

Remember recent search terms in a dropdown so you can re-run a previous search without
retyping; persists across launches.

## Scope

- **In:** make the Search field an editable combo (or attach a completer) holding the
  last N distinct terms; committing a search pushes it to the top; persisted as
  `search_history`.
- **Out:** history for the Exclude/package fields; fuzzy history.

## Design

| File | Layer | Change |
|---|---|---|
| `src/zlog/core/history.py` (new) | core | `push_history(items, term, limit=20)` pure list logic + tests. |
| `src/zlog/core/settings.py` | core | Add `"search_history": []`. |
| `src/zlog/ui/main_window.py` | ui | Search becomes editable `QComboBox` (or keep `QLineEdit` + `QCompleter`); on returnPressed, push the term; persisted via the settings spec. |

## Architecture touch points

- Pure `core.history` list logic; settings stays JSON-able. Search wiring unchanged
  otherwise (same `_apply_search`).
- Versioning: no bump.

## Risks & regressions to check

- Switching Search widget type must keep every existing signal/behavior intact.
- History de-dupes and is capped; round-trips through settings.

## Verification

- [ ] `uv run pytest` (core history tests + round-trip)
- [ ] `uv run ruff check .` and `uv run ruff format --check .`
