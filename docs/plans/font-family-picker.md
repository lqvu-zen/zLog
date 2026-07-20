# Plan: Font-family picker

- **Status:** Done  <!-- Draft | Approved | In progress | Done | Abandoned -->
- **Owner:** Claude
- **Created:** 2026-07-18
- **Related:** readable-log-font.md, font-zoom.md

## Goal

Let the user pick the monospace font family used for the log table and detail
pane from Settings → Appearance (e.g. Cascadia Mono, Consolas, JetBrains Mono),
instead of always using the built-in family chain.

## Scope

- **In:** a chosen family applied to both the table and detail pane, offered as a
  dropdown of the installed fixed-pitch families plus a **Default** entry (the
  existing `LOG_FONT_FAMILIES` chain); persisted.
- **Out (non-goals):** per-widget fonts, font style/weight, proportional fonts,
  font size (that's the existing zoom).

## Design

Two spots build the log font today — `_build_widgets` (the table) and the detail
pane (~line 1626) — both do `QFont(); setFamilies(LOG_FONT_FAMILIES);
setStyleHint(Monospace)`. `_apply_font` then only adjusts point size. Introduce a
single `_make_log_font()` helper that honors `self._font_family` ("" = the
chain) and route all three call sites (table build, detail build, `_apply_font`)
through it so family + size stay in one place.

| File | Layer | Change |
|---|---|---|
| `src/zlog/ui/main_window.py` | ui | Add `self._font_family = ""`. New `_make_log_font() -> QFont`: if `_font_family` set, `setFamily(_font_family)` (with `setFamilies([_font_family, *LOG_FONT_FAMILIES])` so a missing pick still falls back); else the current chain. Always `setStyleHint(Monospace)`, `setFixedPitch(True)`, `setPointSize(BASE_FONT_PT + _font_delta)`. Use it in `_build_widgets`, the detail-pane build, and rewrite `_apply_font` to rebuild the font from it. New `_set_font_family(name)` applies + `_apply_font`. Wire into `_collect_settings`/`_apply_settings_values`/`_settings_specs` (`"font_family"`). |
| `src/zlog/ui/settings_dialog.py` | ui | Appearance tab: a `QComboBox` "Log font", first item **Default** (data `""`), then families passed in via a new `fonts=` ctor arg; select `values["font_family"]`; return from `get_values()`. |
| `src/zlog/core/settings.py` | core | Add `"font_family": ""` to `DEFAULTS`. |

`_open_settings` builds the family list with
`sorted(QFontDatabase.families())` filtered to `QFontDatabase.isFixedPitch(f)`
(both static in PySide6 6.x). Passing the list in (not querying inside the
dialog) keeps `SettingsDialog` a pure view.

## Architecture touch points

- **Threading:** none.
- **Model/proxy:** none — view fonts only.
- **Dependency direction:** unchanged; `QFontDatabase` query stays in `ui`.

## Risks & regressions to check

- A saved family later uninstalled: `setFamilies([pick, *chain])` degrades to the
  chain, so text never disappears.
- Non-fixed-pitch families would break column alignment — the picker only lists
  fixed-pitch families, and `setFixedPitch(True)` still applies.
- `_apply_row_height` derives from `QFontMetrics(self.table.font())`, so a family
  swap with different metrics re-computes row height correctly (it's already
  called at the end of `_apply_font`).

## Verification

- [ ] `uv run pytest` (a headless test can set `_font_family` and assert
      `self.table.font().family()` reflects it after `_apply_font`).
- [ ] `uv run ruff check .` and `uv run ruff format --check .`
- [ ] `run-zlog` driver scenario `font-family`: seed rows, set a known family
      (e.g. Consolas on Windows), screenshot.

## Open questions

- Whether to list *all* families or only fixed-pitch. Decision: fixed-pitch only,
  to protect column alignment.
