# Plan: Clear Filters

- **Status:** Done
- **Owner:** Vũ
- **Created:** 2026-07-06
- **Related:** package-filter.md, regex-search.md

## Goal

One click resets every active filter — min level, text/regex search, and the package
filter — back to "show everything", without clearing the captured log itself.

## Scope

- **In:** a **Clear filters** button on the filter row (and a matching **View → Clear
  Filters** action) that: sets Min level → V, empties the search box and unchecks Regex,
  and clears the package filter. Master list untouched.
- **Out:** clearing the log (that's the existing **Clear** button), resetting theme /
  columns / follow, or a per-filter "reset" affordance.

## Design

Pure UI wiring; no `core`/proxy changes. A `clear_filters()` slot drives the existing
widgets and reuses `clear_package_filter()`; the widgets' own `textChanged` /
`currentIndexChanged` / `toggled` signals push the reset through the proxy, so there's
one code path for "filter changed".

| File | Layer | Change |
|---|---|---|
| `src/zlog/ui/main_window.py` | ui | Add `clear_filters_btn` to row 2 and a **View → Clear Filters** action; add `clear_filters()` that resets level→V, search→"" + regex off, then calls `clear_package_filter()`. |

## Architecture touch points

- **Model/threading:** none. Resets happen on the main thread through existing signals;
  the model stays virtualized and complete (filter-through-the-proxy invariant holds).
- **Dependency direction:** UI-only.
- **Versioning:** no bump.

## Risks & regressions to check

- After Clear filters, all captured rows are visible again (proxy row count == model).
- Search box error tint is cleared (empty pattern is valid).
- No adb calls triggered (package clear is local state only).
- Setting level via `setCurrentIndex(0)` still fires the min-level update.

## Verification

- [ ] `uv run pytest`
- [ ] `uv run ruff check .` and `uv run ruff format --check .`
- [ ] Headless: apply level+text+pid filters, call `clear_filters()`, assert
      `proxy.rowCount() == model.rowCount()` and widgets reset
- [ ] Manual: filter down, click Clear filters → full log returns, boxes cleared
