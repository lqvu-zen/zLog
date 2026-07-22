# Plan: Save/Update filter button on the filter row

- **Status:** Done  <!-- Draft | Approved | In progress | Done | Abandoned -->
- **Owner:** unassigned
- **Created:** 2026-07-22
- **Related:** [filter-presets.md](filter-presets.md), [preset-edit.md](preset-edit.md), [saved-filters-sidebar.md](saved-filters-sidebar.md), [clear-filters-button.md](clear-filters-button.md)

## Goal

Put a single **Save/Update** button on the filter row, immediately left of **Clear
filters**, that adapts to context: with an unsaved filter it reads **Save filter…**
(creates a new preset); while a saved filter is applied it reads **Update ‹name›**
(rewrites that preset with the current — possibly edited — query). Saving/updating a
preset no longer requires the Saved Filters sidebar.

## Scope

- **In:** the new context-aware button; tracking the *applied* preset so edits can
  be saved back to it; removing the now-redundant sidebar **Save current filter…**
  and **Update to current** buttons (sidebar keeps Rename/Delete + double-click apply).
- **Out (non-goals):** auto-saving, a "dirty/unsaved changes" marker, renaming from
  this button, multi-select. One button, two states.

## Design

Add `self._active_preset_name: str | None` — the preset currently "in use". The
button's label/action derive from `_active_preset()` (the dict for that name if it
still exists, else None → treat as unsaved).

**State transitions**
- Applying a preset (`_apply_preset`, incl. sidebar double-click / preset menu) sets
  `_active_preset_name = name`.
- **Clear filters** sets it to `None`.
- The query bar becoming **empty** sets it to `None` (back to Save).
- A non-empty manual edit keeps it (so Update captures the edits — the chosen
  "track applied preset" behavior).
- After **Save…** the new name becomes active; after **Update** it stays active.
- If the active preset is **deleted/renamed away**, `_active_preset()` returns None
  (stale name), so the button falls back to Save.

**Button behavior**
- Unsaved (`_active_preset()` is None): label **Save filter…**, click →
  `save_current_preset()`; on success set `_active_preset_name`. Disabled when the
  query is empty (nothing to save).
- Saved: label **Update ‹name›**, tooltip "Overwrite ‹name› with the current
  filter", click → update that preset (reuse the `make_preset(... query=…)` +
  `upsert_preset` body, targeting `_active_preset_name` instead of the sidebar
  selection).

| File | Layer | Change |
|---|---|---|
| `src/zlog/ui/main_window.py` | ui | New `self.save_update_btn` inserted in `_build_layout`'s `filter_row` **before** `clear_filters_btn`. `_active_preset_name` init in `__init__`; `_active_preset()` helper. `_refresh_save_update_button()` sets label/tooltip/enabled from state; connected to `query.textChanged` and called after apply/clear/save/update/delete/rename and on load. `save_current_preset` sets the active name on success; a new `_save_or_update_active()` slot the button calls. `_apply_preset` sets the active name; `clear_filters` clears it. Remove `self.save_filter_btn` / `self.update_filter_btn` creation, their `_build_layout` rows, and their `_connect_signals` wiring; keep `_update_preset_to_current` only if still referenced (else delete). Command-palette parity: expose the new action. |
| `docs/GUIDE.md` | — | Update the Filter-presets section: the filter-row Save/Update button is the primary path; sidebar keeps Rename/Delete + double-click apply. |
| `tests/test_main_window_presets.py` | — | Button reads "Save…" with a fresh query; after applying a preset it reads "Update ‹name›"; editing keeps Update and Update rewrites the preset's query; Clear filters / emptying the query flips back to Save; deleting the active preset flips back to Save. |

## Architecture touch points

- **Threading:** none.
- **Model/proxy:** none — presets are settings state; the button only reads the
  query bar and writes `self._presets` (persisted via `_save_settings`).
- **Dependency direction:** UI-only; `core/presets.py` (`make_preset`, `upsert_preset`,
  `preset_summary`) unchanged.

## Risks & regressions to check

- Removing the two sidebar buttons must not break `_connect_signals` (drop their
  `.clicked.connect`) or the presets test that referenced them — update those.
- The active-preset name can go stale (delete/rename): `_active_preset()` must
  re-check membership every time, never cache a dict.
- Programmatic query changes (`_set_query_text` from apply/isolate/tab-switch/level
  sync) fire `textChanged` → `_refresh_save_update_button`; ensure applying a preset
  sets the active name *after* `_set_query_text` so the empty-query reset doesn't
  immediately clear it.
- Empty-query rule vs. applying a preset whose query is empty (e.g. a "clear
  everything" preset): applying it sets the active name, but the empty-query reset
  would immediately null it. Decide: the empty-query reset only fires on a *user*
  edit, not on `_apply_preset` (guard with the same signal-block `_set_query_text`
  already uses, or set the active name in a way the reset respects).
- Command palette / menu entries that pointed at the old sidebar actions.

## Verification

- [ ] `uv run pytest` (new/updated `test_main_window_presets.py`)
- [ ] `uv run ruff check .` and `uv run ruff format --check .`
- [ ] `run-zlog` scenario: fresh query shows Save; apply a preset shows Update ‹name›;
      edit + Update rewrites it; Clear flips back to Save (screenshot each state).

## Open questions

- Exact label: **Update ‹name›** (name inline) vs. plain **Update filter** with the
  name only in the tooltip. Leaning name-inline when it fits, eliding long names.
- Should applying a preset also select it in the sidebar list (visual consistency)?
  Minor; leaning yes if cheap.
