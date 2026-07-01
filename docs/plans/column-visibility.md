# Plan: Column show/hide toggles

- **Status:** Done  <!-- Draft | Approved | In progress | Done | Abandoned -->
- **Owner:** Vũ
- **Created:** 2026-07-01
- **Related:** persists via `settings-persistence.md`

## Goal

Let the user hide columns they don't need (e.g. TID, or PID) from a **View →
Columns** menu, and remember the choice across launches.

## Scope

- **In:** a checkable action per column under **View → Columns**; toggling hides/shows
  that column. Hidden columns are persisted and restored on launch.
- **Out:** reordering columns; per-column width persistence.

## Design

| File | Layer | Change |
|---|---|---|
| `src/zlog/core/settings.py` | core | add `"hidden_columns": []` to `DEFAULTS`. |
| `src/zlog/ui/main_window.py` | ui | Import `COLUMNS`; build a **View → Columns** submenu with a checkable action per column bound to `self.table.setColumnHidden(col, not checked)`. Load/save the hidden set in `_load_and_apply_settings` / `_save_settings`. |
| `.claude/skills/run-zlog/scripts/driver.py` | (skill) | a `columns` scenario hiding PID/TID for a screenshot. |

## Architecture touch points

- **Model/threading:** none. Column visibility is a view setting; the model is
  untouched and stays virtualized.
- **Dependency direction:** UI-only + one pure `DEFAULTS` key. `core` stays Qt-free.
- **Versioning:** no bump (release-only).

## Risks & regressions to check

- Hiding/showing updates immediately; Message keeps stretching when neighbors hide.
- Hidden set persists and restores on reopen.
- Hiding all-but-one degrades gracefully (no crash); user can restore from the menu.

## Verification

- [x] `uv run pytest`
- [x] `uv run ruff check .` and `uv run ruff format --check .`
- [x] `run-zlog` `columns` screenshot shows PID/TID hidden
- [ ] Manual: hide a column, reopen → still hidden; re-show it
