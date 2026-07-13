# Plan: Preview / edit / override saved filters

- **Status:** Done
- **Owner:** unassigned
- **Created:** 2026-07-11
- **Related:** [saved-filters-sidebar.md](saved-filters-sidebar.md), [filter-presets.md](filter-presets.md)

## Goal

After this ships, the Saved Filters sidebar can **preview** a filter (readable
summary + per-item tooltip), **Update to current** (overwrite the selected filter
with the current filter), and **Rename** a filter.

## Scope

- **In:** a pure `preset_summary(preset)`; a preview label + item tooltips;
  Update-to-current and Rename buttons wired to the existing preset upsert/remove.
- **Out:** a full field-by-field edit dialog (Update-to-current + Rename cover it),
  drag-reorder, duplicate.

## Design

| File | Layer | Change |
|---|---|---|
| `src/zlog/core/presets.py` | core | `preset_summary(preset) -> str` — readable filter (`level:E package:… /re/ (case-sensitive)`, or `(show everything)`). Pure. |
| `src/zlog/ui/main_window.py` | ui | Import `preset_summary`. Sidebar: add `update_filter_btn`, `rename_filter_btn`, and a muted word-wrapped `preset_preview` label. `_rebuild_presets_list` sets each item's tooltip to the summary and refreshes the preview. `_selected_preset()`; `_update_preset_preview()` (on selection change); `_update_preset_to_current()` (upsert same name from the current filter widgets); `_rename_preset()` (QInputDialog → remove old + upsert renamed). |
| `tests/test_presets.py`, `tests/test_main_window_settings.py` | tests | `preset_summary` formatting; update overwrites the selected preset's fields; rename changes the name and keeps the fields. |

## Architecture touch points

- **Reuses** `make_preset`/`upsert_preset`/`remove_preset` + persistence; summary is
  pure/tested. No new filtering path.

## Risks & regressions to check

- **No selection:** Update/Rename are no-ops with a hint; Preview clears.
- **Rename collisions:** upsert is by name (case-insensitive), so renaming onto an
  existing name replaces it — acceptable.
- **Update reads current widgets** (level/search/regex/case/package) — same source as
  Save, so it stays consistent.

## Verification

- [ ] `uv run pytest`
- [ ] `uv run ruff check .` and `uv run ruff format --check .`
- [ ] Manual: select a filter → preview shows; Update to current overwrites; Rename works.
