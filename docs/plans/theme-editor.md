# Plan: Theme editor (custom colors)

- **Status:** Done  <!-- Draft | Approved | In progress | Done | Abandoned -->
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

- [x] `uv run pytest` (round-trip + fallback + dialog seeding)
- [x] `uv run ruff check .` and `uv run ruff format --check .`
- [x] `run-zlog` smoke screenshot (app still launches with the new import graph)
- [ ] Manual: edit a level color, see the log repaint live; save, restart, confirm
      the custom theme is still there and selected.

## Resolved

- **Scope of tokens:** exposed all ~20 fields, grouped into three `QGroupBox`
  sections (General / Level backgrounds / Level text) rather than a flat wall —
  skipped the "advanced" collapsible section since three grouped forms already
  read cleanly; can add one later if the dialog grows.
- **Base:** yes — seeded from `THEMES[self._theme_name]`, the currently applied
  theme.
- **Export/import as JSON:** left out, as leaned — not asked for.
- **Name collision:** reject (a `QMessageBox.warning` + re-prompt loop), not
  suffix — silently renaming what you typed is more surprising than asking again.

## Architecture note (not in the original plan)

The plan put `core/theme_io.py` in `core/` but assumed `Theme` stays defined in
`ui/theme.py` — that would make a `core/` module import from `ui/`, backwards
per `ui → adb → core`. Fixed by moving `Theme` + the built-in instances +
`THEMES` into a new **`core/theme.py`** (still Qt-free, now actually in the
right layer); `ui/theme.py` re-exports them unchanged plus `build_stylesheet`
and the new `register_theme`, so every existing `from zlog.ui.theme import …`
elsewhere in the codebase kept working with no call-site changes.

## Implementation notes

- `core/theme_io.py`: `theme_to_dict` is `dataclasses.asdict`; `theme_from_dict`
  validates every field independently (including each key inside
  `level_colors`/`level_text`) and falls back to `base`'s value per-field, so a
  hand-edited or corrupted settings file degrades one color at a time rather
  than breaking the whole theme.
- `ui/theme_editor.ThemeEditorDialog` edits its own working `Theme` via
  `dataclasses.replace` and calls `on_preview(theme)` — wired to a new
  `MainWindow._apply_theme_object(theme)` (the guts of the old `apply_theme`,
  now split so it can restyle from a `Theme` object directly, not just a
  registered name) — so every edit repaints the log live, exactly like
  switching a built-in theme already did.
- Settings gained a `custom_themes` key that **must load before `theme`** (see
  the ordering comment at its spec entry) — `apply_theme(name)` does
  `THEMES[name]`, so a saved custom theme has to be registered first or it
  raises `KeyError` instead of the plan's original worry ("silently falls back
  to Light"); a spec-order bug during implementation caused the newly-saved
  theme's radio action to not show checked (fixed by calling `apply_theme`
  before `_rebuild_theme_actions`, not after) — caught by
  `test_open_theme_editor_registers_and_applies_custom_theme`.
- A settings entry whose name collides with a built-in (e.g. a hand-edited
  `"Dark"`) is skipped on load rather than crashing or overwriting the real
  built-in — covered by
  `test_settings_load_skips_custom_theme_colliding_with_builtin`.
