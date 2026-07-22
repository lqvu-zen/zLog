# Plan: Saved-filter right-click menu (Add / Edit / Rename / Delete)

- **Status:** Done  <!-- Draft | Approved | In progress | Done | Abandoned -->
- **Owner:** unassigned
- **Created:** 2026-07-22
- **Related:** [saved-filters-sidebar.md](saved-filters-sidebar.md), [preset-edit.md](preset-edit.md), [save-update-filter-button.md](save-update-filter-button.md), [filter-presets.md](filter-presets.md)

## Goal

Manage saved filters from a **right-click menu** on the Saved Filters list instead
of dedicated buttons: **Apply**, **Add…** (create a new preset from a Name+Query
editor, query pre-filled with the current filter), **Edit…** (change the selected
preset's query), **Rename…** (name only), **Delete**. The Rename/Delete buttons
under the list are removed.

## Scope

- **In:** a `customContextMenuRequested` menu on `presets_list`; a small Name+Query
  editor dialog reused by Add and Edit; wiring for Add/Edit; removal of the
  Rename/Delete buttons. Item-specific actions (Apply/Edit/Rename/Delete) act on the
  right-clicked row; Add is always available.
- **Out (non-goals):** drag-reorder, multi-select, folders/tags, editing the level
  floor/case as separate fields (they live in the query text or carry over). One
  query editor.

## Design

Presets already store the raw **query** as the source of truth (`preset["query"]`),
with decomposed `min_level/search/regex/case/package` kept for the summary/legacy
apply path (see `preset-save-full-query.md`). Add/Edit therefore center on the query
text; a helper parses it (`core.query.parse_query`) to fill the decomposed fields so
`preset_summary` and legacy apply stay correct.

| File | Layer | Change |
|---|---|---|
| `src/zlog/ui/preset_dialog.py` (new) | ui | `PresetDialog(QDialog)` with a **Name** line edit and a **Query** line edit (+ OK/Cancel). Ctor `(title, name="", query="", name_editable=True)`; `get_values() -> (name, query)`. Name field disabled when `name_editable=False` (Edit keeps the name). Blank name blocks OK for Add. Pure view — no model/preset knowledge. |
| `src/zlog/ui/main_window.py` | ui | `presets_list.setContextMenuPolicy(CustomContextMenu)` + `customContextMenuRequested → _show_presets_menu(pos)`. The menu: **Apply** (item), separator, **Add…** (always), **Edit…** (item), **Rename…** (item), **Delete** (item). New `_add_preset()` (dialog seeded with `self.query.text()`; on accept build via `_preset_from_query(name, query)` → `upsert_preset`, refresh, save). New `_edit_preset(preset)` (dialog seeded with `preset["query"]`, name read-only; on accept rebuild that preset's query, keep its `case`, `upsert`, refresh, save; if it's the active preset, `_refresh_save_update_button`). Add `_preset_from_query(name, query, base=None)` helper (parse_query → make_preset(name, min_level=spec.level or "V", search=spec.search, regex=spec.regex, case=base["case"] if base else self.case_check.isChecked(), package=spec.package, query=query)). Remove `self.rename_filter_btn`/`self.delete_filter_btn` creation, their `_build_layout` row, and their `_connect_signals` wiring; keep `_rename_preset`/`_delete_selected_preset` (now menu-invoked, operating on the right-clicked item). |
| `docs/GUIDE.md` | — | Filter-presets section: right-click a saved filter for Apply/Add/Edit/Rename/Delete; double-click still applies. |
| `tests/test_main_window_presets.py` | — | `_add_preset` creates a preset with the typed name+query (mock the dialog); `_edit_preset` rewrites the query, keeps the name; editing the active preset keeps it active + refreshes the button; a menu smoke asserts the actions exist. |

## Architecture touch points

- **Threading:** none.
- **Model/proxy:** none — presets are settings state; `core/presets.py` unchanged.
- **Dependency direction:** `ui.preset_dialog` imports only Qt; `main_window` builds
  presets via `core.presets` + `core.query`. `ui → core` holds.

## Risks & regressions to check

- The context menu must target the **right-clicked** item (`itemAt(pos)`), not just
  the current selection, so right-click reliably acts on what's under the cursor
  (fall back to `currentItem` if the click missed a row → only Add enabled).
- `_selected_preset()`/`_delete_selected_preset`/`_rename_preset` currently read
  `currentItem`; either set the current row from the right-clicked item before
  invoking them, or pass the preset explicitly. Prefer passing the preset dict.
- Removing the buttons must drop their `_connect_signals` lines and any test that
  referenced them (grep first).
- Editing the **active** preset (the one the Save/Update button tracks) must refresh
  that button (name unchanged, so it stays "Update ‹name›").
- Parsing a hand-typed query for the decomposed fields must not crash on bad regex
  (`parse_query` is tolerant; `preset_summary` prefers the raw query anyway).
- Empty query in Add/Edit is allowed (a "show everything" preset) — only a blank
  **name** blocks Add.

## Verification

- [ ] `uv run pytest` (updated `test_main_window_presets.py`)
- [ ] `uv run ruff check .` and `uv run ruff format --check .`
- [ ] `run-zlog` scenario: right-click a preset → menu with Apply/Add/Edit/Rename/
      Delete; Add creates one; Edit changes its summary (screenshot the menu).

## Open questions

- Menu when clicking empty space (no item): show only **Add…** (recommended) vs. the
  full menu with item actions disabled. Leaning Add-only.
- Keep a visible **Add** affordance too (the list is otherwise button-less)? The
  filter-row **Save** button already covers "save current filter", so right-click
  Add is enough; leaning no extra button.
