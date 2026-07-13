# Plan: Saved-filters sidebar

- **Status:** Done
- **Owner:** unassigned
- **Created:** 2026-07-11
- **Related:** [filter-presets.md](filter-presets.md) (the preset backend this reuses)

## Goal

After this ships, a left **Saved Filters** panel lists your saved filter presets;
double-click one to apply it, and a **Save current filter…** button stores the
current filter under a name. (The existing View → Presets menu keeps working.)

## Scope

- **In:** a dockable left panel with a presets `QListWidget`, a Save button, and a
  Delete button; double-click/Enter applies; View menu toggles the panel. Reuses
  the existing `save_current_preset`/`_apply_preset`/`_delete_preset` + persistence.
- **Out:** drag-reorder, per-preset colors/icons, folders, editing a preset in place
  (delete + re-save), remembering the dock's shown/floating state.

## Design

| File | Layer | Change |
|---|---|---|
| `src/zlog/ui/main_window.py` | ui | Import `QDockWidget`. In `_build_widgets`, create `presets_list` (`QListWidget`), `save_filter_btn`, `delete_filter_btn`. In `_build_layout`, wrap them in a panel inside a left `QDockWidget` (`addDockWidget(Qt.LeftDockWidgetArea, …)`). `_rebuild_presets_list()` populates the list from `self._presets`; call it at the end of the existing `_rebuild_presets_menu()` so save/delete/load already refresh both. `_on_preset_activated(item)` → `_apply_preset`; `_delete_selected_preset()` → `_delete_preset`. Add the dock's `toggleViewAction()` to the View menu. |
| `tests/test_main_window_settings.py` | tests | Presets populate the list; activating an item applies its query; deleting the selected removes it. |

## Architecture touch points

- **Pure preset core reused** (`core/presets.py`); this is view-only wiring over the
  same single filtering code path (presets → query string → proxy).
- **`QMainWindow` docks** natively, so no central-layout restructuring.

## Risks & regressions to check

- **Build order:** `presets_list` is created in `_build_widgets` (before
  `_build_menus` calls `_rebuild_presets_menu`), so the list refresh is safe.
- **Menu still works:** the View → Presets submenu and the sidebar stay in sync
  (both refreshed by `_rebuild_presets_menu`).

## Verification

- [ ] `uv run pytest`
- [ ] `uv run ruff check .` and `uv run ruff format --check .`
- [ ] Screenshot: left Saved Filters panel with entries; double-click applies.
