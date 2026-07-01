# Plan: Theming + dark mode

- **Status:** Done  <!-- Draft | Approved | In progress | Done | Abandoned -->
- **Owner:** Vũ
- **Created:** 2026-06-30
- **Related:** consolidates `LEVEL_COLOR` and the regex-error tint into one place;
  the `review-zlog-ui` skill and `CLAUDE.md` both anticipate `ui/theme.py`

## Goal

Give zLog a **Light** and a **Dark** theme, switchable at runtime from the menu, so
the log table (and level tints) are comfortable to read for long sessions — and
centralize every color in one `ui/theme.py` instead of scattered hex values.

## Scope

- **In:**
  - A **View → Theme → Light / Dark** menu (exclusive, checkable); Light is default.
  - A `ui/theme.py` holding all color tokens: window/text/base/header colors, the
    per-level row tints (W/E/F), and the invalid-regex tint.
  - The level row tints and the invalid-regex tint come from the active theme, so
    both look right on light and dark backgrounds.
  - Switching theme restyles the whole window and repaints the table live.
- **Out (non-goals):**
  - Persisting the chosen theme across launches (needs a settings file — future).
  - Following the OS light/dark preference automatically.
  - User-customizable/arbitrary themes; per-tag colors.

## Design

Keep `ui/theme.py` **Qt-free** (pure strings) so it's unit-testable: it defines the
palette as hex strings and builds a Qt stylesheet string; the model converts the
level hex values to `QColor`.

| File | Layer | Change |
|---|---|---|
| `src/zlog/ui/theme.py` (new) | ui | `Theme` dataclass (name + `window/text/base/alt_base/header` hex, `level_colors: dict[str,str]` for W/E/F, `search_error` hex); `LIGHT`, `DARK`, `THEMES = {name: Theme}`; `build_stylesheet(theme) -> str` returning app-wide QSS. No Qt import. |
| `src/zlog/ui/log_model.py` | ui | Replace the module-level `LEVEL_COLOR` with per-instance `self._level_colors` (default from `theme.LIGHT`), plus `set_level_colors(hexmap)` that rebuilds `QColor`s. `data()` reads `self._level_colors`. |
| `src/zlog/ui/main_window.py` | ui | Add a **View** menu with a `QActionGroup` of themes. `apply_theme(name)`: `QApplication.instance().setStyleSheet(build_stylesheet(theme))`, `model.set_level_colors(theme.level_colors)`, repaint the table viewport, and remember `theme.search_error` for the regex tint. Route the existing invalid-regex tint through this instead of the hard-coded hex. Apply Light on startup. |
| `tests/test_theme.py` (new) | tests | `THEMES` has Light + Dark; each has W/E/F level colors as `#…` hex; `build_stylesheet(DARK)` is a str containing the window color. Pure, no Qt. |
| `.claude/skills/run-zlog/scripts/driver.py` | (skill) | a `dark` scenario: `window.apply_theme("Dark")`, seed sample rows, screenshot. |

## Architecture touch points

- **Threading:** none — pure styling on the main thread.
- **Model/proxy:** unchanged filtering; only the `BackgroundRole` color source moves
  to a per-instance, theme-driven map. Still virtualized; a theme switch triggers a
  `viewport().update()` repaint (no model reset, no per-row widgets).
- **Dependency direction:** `ui/theme.py` is Qt-free config imported by `ui`
  widgets/model. Nothing new crosses `core`.
- **Centralize colors:** this is the "move tokens into a single `ui/theme.py`" step
  the docs call for; after it, no widget hard-codes a hex (the regex tint included).
- **Versioning:** no version bump (versions change only at release).

## Risks & regressions to check

- Level tints stay readable in both themes (light text on dark tints, dark text on
  light tints); confirm via screenshots.
- Switching theme repaints existing rows immediately (not just new ones).
- The invalid-regex tint uses the theme color and clears correctly on a valid regex.
- Default Light theme looks the same as today (no unintended visual drift).
- Menu bar now has File + View; both work.

## Verification

- [x] `uv run pytest` (new `test_theme.py` green)
- [x] `uv run ruff check .` and `uv run ruff format --check .`
- [x] `run-zlog` `dark` screenshot shows a readable dark table; `populated` (light)
      still looks right
- [ ] Manual: toggle Light/Dark at runtime → whole window + existing rows restyle

## Open questions

- Menu location: **View → Theme → Light/Dark** (proposed) vs a toolbar toggle?
- Dark level tints: muted dark backgrounds keeping the light message text (proposed)
  — or colored text on a flat dark row instead?
- Default theme **Light** (proposed) vs Dark for a log tool?
