# Plan: Plugin hooks (custom row colorizers)

- **Status:** Done
- **Owner:** unassigned
- **Created:** 2026-07-11
- **Related:** ROADMAP v2.0 (plugin hooks), [tag-highlight.md](tag-highlight.md)

## Goal

After this ships, a user can drop a `.py` file in a plugins folder that defines
`colorize(entry) -> hex | None`; matching rows get that background tint. It's a
minimal, opt-in extension point for custom highlighting rules.

## Scope

- **In:** load `colorize` callables from a plugins directory; apply them (first
  non-None wins) as a row tint below explicit tag highlights; a View → Reload
  Plugins action; errors isolated per file.
- **Out:** custom parsers (colorizers only for now), sandboxing (plugins are
  trusted user code), a plugin manager UI, hot-reload on file change.

## Design

| File | Layer | Change |
|---|---|---|
| `src/zlog/core/plugins.py` | core | `load_colorizers(directory) -> (list[callable], list[str])` — exec each non-`_` `.py`, collect its `colorize`; per-file errors captured, never raised. `apply_colorizers(colorizers, entry) -> str | None` — first non-None, swallowing exceptions. Pure application logic (testable with fake callables/dirs). |
| `src/zlog/ui/log_model.py` | ui | `set_colorizers(fns)`; in `BackgroundRole` and `HIGHLIGHT_ROLE` (what the delegate paints), after the explicit tag color and before search-highlight, return `QColor(apply_colorizers(...))` if a plugin returns one. |
| `src/zlog/ui/main_window.py` | ui | `_plugins_dir()` = `<AppDataLocation>/plugins`; `_load_plugins()` creates it, loads, `model.set_colorizers`, and reports count/errors. Called on startup; View → **Reload &Plugins**. |
| `tests/test_plugins.py`, `tests/test_log_model.py` | tests | Loader finds a temp `colorize` plugin, skips a broken one; `apply_colorizers` precedence; a colorizer tints a row via `HIGHLIGHT_ROLE`. |

## Architecture touch points

- **core stays import-safe:** `apply_colorizers` is pure; `load_colorizers` does the
  file IO/exec (trusted plugins), isolated with try/except per file.
- **Precedence:** explicit tag highlight > plugin colorizer > search highlight >
  level tint — so plugins don't override a user's manual tag color.

## Risks & regressions to check

- **Bad plugin:** a syntax/runtime error in one file is captured and skipped; the
  others still load; a colorizer that raises per-row is swallowed.
- **Hot path:** `apply_colorizers` runs only for visible rows (delegate), and only
  when plugins exist.
- **No plugins dir:** returns empty, no error.

## Verification

- [ ] `uv run pytest`
- [ ] `uv run ruff check .` and `uv run ruff format --check .`
- [ ] Manual: drop a colorize plugin, Reload Plugins, matching rows tint.
