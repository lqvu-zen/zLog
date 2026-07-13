# Plan: Presets save the whole query (fix "only saves the level")

- **Status:** Done
- **Owner:** unassigned
- **Created:** 2026-07-13
- **Related:** [filter-presets.md](filter-presets.md), [saved-filters-sidebar.md](saved-filters-sidebar.md), [preset-edit.md](preset-edit.md)

## Problem

Saving a filter preset only round-trips the **level**. A preset captured only
`search/regex/package` decomposed from the query bar, so `tag:` and `-exclude`
tokens (and the plain word when a regex was also present) were **dropped** — the
query bar is the real filter, and it holds more than those fields.

## Fix

Store the **raw query-bar text** as the preset's source of truth (`query` field),
alongside the level floor (which lives in the dropdown, not the query) and `case`.
Applying a preset sets the level + case and pastes the query back verbatim, so every
token survives. Old fields stay for backward-compatible loading and the summary.

| File | Layer | Change |
|---|---|---|
| `src/zlog/core/presets.py` | core | `make_preset` gains `query=""`; `normalize_presets` carries it; `preset_summary` prefers `query` when present (`level:E  tag:Foo -spam`). |
| `src/zlog/ui/main_window.py` | ui | `save_current_preset` / `_update_preset_to_current` store `query=self.query.text()`. `_apply_preset` prefers `preset["query"]` (falls back to the old search/package reconstruction for legacy presets). `_rename_preset` preserves `query`. |
| tests | | round-trip a `tag:`/`-exclude` query through save→apply; legacy preset (no `query`) still applies. |

## Verification

- [ ] `uv run pytest`
- [ ] ruff clean on touched files
- [ ] Manual: type `tag:Foo -spam`, Save, Clear, apply → query bar comes back intact.
