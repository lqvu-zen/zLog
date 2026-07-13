# Plan: Two-way sync between the Level dropdown and the query

- **Status:** Done
- **Owner:** unassigned
- **Created:** 2026-07-14
- **Related:** [min-level-selector.md](min-level-selector.md), [level-multiselect.md](level-multiselect.md)

## Problem

The Level dropdown and the query bar's `level:` token could disagree. Changing the
dropdown updated the proxy floor but not the query text; a `level:` token in the
query would silently override a later dropdown change. The two were not in sync.

## Fix — one source of truth

Make the query bar's `level:` token the single source of truth; the dropdown is a
two-way mirror:

- **Dropdown → query:** a user change writes/replaces `level:<X>` in the query (or
  drops it for V). `_apply_query` then re-applies the whole filter from the query.
- **Query → dropdown:** `_apply_query` reflects the query's level into the dropdown
  (guarded so it doesn't rewrite the query back — no signal loop).
- A query with no `level:` token means floor V; the dropdown follows. Clearing the
  query therefore also clears the level floor (they stay in sync).

| File | Change |
|---|---|
| `src/zlog/ui/main_window.py` | Add `_syncing_level` guard. Dropdown signal → `_on_level_box_changed` → `_set_query_level`. `_apply_query` sets the proxy floor authoritatively and mirrors into the dropdown via guarded `_set_level_box`. `clear_filters` just clears the query. `_load_toolbar` relies on the session's query (which carries the level token). `_apply_preset` folds the level into the query. Settings `set_min_level` writes the query token. |
| tests | Update level/clear expectations to the mirror semantics; add a dropdown↔query sync test. |

## Risks

- **Signal loop:** prevented by `_syncing_level` around programmatic dropdown sets.
- **Multi-select `level:W,E`:** leaves the single-select dropdown untouched (as before);
  changing the dropdown then replaces the set with a single floor.
- **Behavior change:** clearing the query now also resets the level floor (previously
  the dropdown kept it). This is the point of the sync.

## Verification

- [ ] `uv run pytest`
- [ ] ruff clean
- [ ] Manual: pick a level → query shows `level:X`; type `level:W` → dropdown follows;
  clear the query → dropdown returns to Verbose.
