# Plan: Bring back a visible min-level selector

- **Status:** Done
- **Owner:** unassigned
- **Created:** 2026-07-11
- **Related:** [level-multiselect.md](level-multiselect.md),
  [logcat-style-ui.md](logcat-style-ui.md) (folded filters into the query bar)

## Goal

After this ships, a visible **Level** dropdown on the filter row sets the minimum
log level (V/D/I/W/E/F), coexisting with the query bar: the query's `level:` token
still works and drives the dropdown, and when the query has no `level:` the
dropdown is the min-level source.

## Why

The redesign folded min-level into the query bar (`level:E`) and left the
`level_box` as hidden state. Users want a one-click level floor without typing a
token — the most common logcat filter. The widget already exists and is wired to
`proxy.set_min_level`; it just needs to be placed and to stop being reset by the
query on every keystroke.

## Scope

- **In:** show `level_box` (with a "Level:" label) on the filter row before the
  query; make `_apply_query` treat the dropdown as the floor source unless the
  query names a `level:`; make Clear Filters reset it to V.
- **Out:** replacing the query `level:`/`level:W,E` syntax (still supported), a
  multi-select popup (exact sets stay query-only), reordering other controls.

## Design

| File | Layer | Change |
|---|---|---|
| `src/zlog/ui/main_window.py` | ui | `_build_widgets`: add a tooltip to `level_box`. `_build_layout`: on the filter row add `QLabel("Level:")` + `self.level_box` before `self.query`. `_apply_query`: in the non-exact branch, only `setCurrentIndex` from `spec.level` when the query actually names one; otherwise apply the dropdown's own floor (`proxy.set_min_level(level_box.currentData())`) instead of forcing it back to "V". `clear_filters`: reset `level_box` to "V" before clearing the query. |
| `tests/test_main_window_settings.py` | tests | The visible dropdown floors the view; a non-`level:` query keeps that floor; Clear Filters restores V (all rows). Existing `level:`-token and persistence tests stay green. |

## Architecture touch points

- **Proxy precedence unchanged:** exact `levels` (from `level:W,E`) still wins over
  the floor; the dropdown only sets the floor.
- **Persistence:** `min_level` already saves/restores via `level_box`; now the
  restored value is visible.

## Risks & regressions to check

- **Query no longer stomps the dropdown:** confirm a plain search query doesn't
  reset the level floor to V (the whole point), and that `level:E` still moves the
  dropdown to E.
- **Clear Filters:** must return the dropdown to V and show everything.
- **Exact-set mode:** with `level:W,E` active, the dropdown floor is ignored (by
  proxy precedence) — acceptable; no crash.

## Verification

- [ ] `uv run pytest`
- [ ] `uv run ruff check .` and `uv run ruff format --check .`
- [ ] Screenshot: filter row shows the Level dropdown before the query box.

## Follow-up (shipped)

Per feedback, the Level dropdown moved onto the top control bar (after Package,
behind a divider) instead of the filter row, and shows full level names
(Verbose/Debug/Info/Warn/Error/Fatal) while its item *data* stays the single
letter — so filtering, `level:` sync, and `min_level` persistence are unchanged.
