# Plan: Theme editor (custom colors)

- **Status:** Draft  <!-- Draft | Approved | In progress | Done | Abandoned -->
- **Owner:** unassigned
- **Created:** 2026-07-24
- **Related:** [theming-dark-mode.md](theming-dark-mode.md), [settings-dialog.md](settings-dialog.md), [persistent-highlight-rules.md](persistent-highlight-rules.md)

## Goal

Edit zLog's colors and save the result as your own theme — pick your level colors,
background, and metadata text instead of choosing among the built-ins.

## Scope

- **In:** a Settings → Appearance editor listing the `Theme` tokens with color
  swatches, live preview, and Save-as/Reset; custom themes persist and appear in
  the theme menu beside the built-ins.
- **Out (non-goals):** importing other editors' theme formats (VS Code, iTerm),
  per-tab themes, and theming individual widgets beyond the existing token set.

## Design

`ui/theme.py` is already the single place colors live: a frozen `Theme` dataclass
of hex strings plus `THEMES` and `build_stylesheet`. A custom theme is therefore
just a `Theme` built from stored values — no new plumbing, and `apply_theme`
already re-styles everything.

| File | Layer | Change |
|---|---|---|
| `src/zlog/core/theme_io.py` (new) | core | Pure: `theme_to_dict(theme)`, `theme_from_dict(data, base)` — validate each hex (`#rgb`/`#rrggbb`), fall back to the base theme's value for anything missing or malformed, so a hand-edited settings file can never produce an unreadable UI. Unit-tested. |
| `src/zlog/ui/theme.py` | ui | `register_theme(theme)` to add a custom entry to `THEMES` at runtime; keep the built-ins immutable. |
| `src/zlog/ui/theme_editor.py` (new) | ui | `ThemeEditorDialog`: a form of token rows (label + swatch button → `QColorDialog` + hex field), seeded from the current theme. Live-applies as you change a value, with Revert. Save prompts for a name. Groups tokens (window/text/base…, level colors, level text) so it isn't one flat wall of 20 fields. |
| `src/zlog/ui/settings_dialog.py` | ui | An "Edit theme…" button on the Appearance tab. |
| `src/zlog/ui/main_window.py` | ui | Persist custom themes via a `custom_themes` entry in the existing `_settings_specs` table; register them at startup **before** the theme is applied, and add them to the theme action group. |
| `tests/test_theme_io.py`, `tests/test_theme_editor.py` (new) | — | Pure: round-trip, bad hex falls back, missing key falls back. Dialog: seeds from the current theme, edits produce a valid `Theme`, Save yields a registered entry. |

## Architecture touch points

- **Threading:** none.
- **Model/proxy:** none — but the model caches `QColor`s from the theme, so a live
  edit must trigger the same refresh path `apply_theme` already uses (and repaint
  the view), or edits appear only on new rows.
- **Dependency direction:** validation is Qt-free in `core/`; the dialog is `ui/`.

## Risks & regressions to check

- **Unreadable combinations** (text == background). Don't block it, but the
  editor should show a live preview row so it's obvious, and Reset must always
  restore a built-in.
- **Startup order:** custom themes must register before `apply_theme` runs during
  settings load, or a saved custom theme silently falls back to Light.
- **Model color cache** — verify existing rows re-tint on a live edit.
- **Settings size/robustness:** a corrupt custom theme must not break loading of
  *all* settings (validate per field, fall back per field).
- Name collision with a built-in ("Dark") — reject or suffix.

## Verification

- [ ] `uv run pytest` (round-trip + fallback + dialog seeding)
- [ ] `uv run ruff check .` and `uv run ruff format --check .`
- [ ] `run-zlog` screenshot of the editor and of a custom theme applied
- [ ] Manual: edit a level color, see the log repaint live; save, restart, confirm
      the custom theme is still there and selected.

## Open questions

- **Scope of tokens:** expose all ~20, or a curated subset (background, text,
  level colors) with "advanced" for the rest? Leaning curated + advanced.
- **Base:** always start from the currently applied theme? Leaning yes.
- Export/import a theme as a small JSON file for sharing? Cheap once
  `theme_io` exists — but out of scope unless asked.
