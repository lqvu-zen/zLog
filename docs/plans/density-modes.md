# Plan: Density modes

- **Status:** Done  <!-- Draft | Approved | In progress | Done | Abandoned -->
- **Owner:** Claude
- **Created:** 2026-07-18
- **Related:** readable-log-font.md, font-zoom.md

## Goal

Let the user choose how tightly log rows pack — **Compact**, **Comfortable**, or
the current **Default** — from Settings → Log view, so a dense triage session
and a relaxed read each get sensible row spacing.

## Scope

- **In:** a per-row vertical padding chosen from three presets, applied to both
  the fixed row height and the delegate's `sizeHint` (wrap mode); persisted.
- **Out (non-goals):** horizontal padding, font size (that's the existing zoom),
  column widths.

## Design

Row height today is `fm.height() + 4` in two places that must agree: the
delegate's `sizeHint` (`return QSize(0, line_h + 4)`) and
`_apply_row_height` (`vh.setDefaultSectionSize(fm.height() + 4)`). The `+4` is
the vertical padding. Make that padding a single delegate attribute, `row_pad`,
read by both, and drive it from a density preset.

A tiny pure map keeps the preset→pixels logic Qt-free and testable.

| File | Layer | Change |
|---|---|---|
| `src/zlog/core/density.py` | core | New. `DENSITY_PAD = {"compact": 2, "default": 4, "comfortable": 8}` and `density_pad(name) -> int` (falls back to the default). Trivial but unit-tested and keeps the constant out of the widget. |
| `src/zlog/ui/log_delegate.py` | ui | Add `self.row_pad = 4` in `__init__`; replace the two literal `+ 4`s in `sizeHint` (the one-line early-return and the wrapped-height return) with `+ self.row_pad`. The chip/band math uses `fm.height() + 4` for the metadata band in wrap mode — also swap to `row_pad` so the chip stays vertically centered. |
| `src/zlog/ui/main_window.py` | ui | Add `self._density = "default"`. New `_set_density(name)`: set `self.log_delegate.row_pad = density_pad(name)`, then `_apply_row_height()` + `self.table.viewport().update()`. `_apply_row_height` uses `fm.height() + self.log_delegate.row_pad`. Wire into `_collect_settings`/`_apply_settings_values` and `_settings_specs` (`"density"`). |
| `src/zlog/ui/settings_dialog.py` | ui | Log view tab: a `QComboBox` "Row density" with Compact/Default/Comfortable (data = the slug); seed from `values["density"]`; return it from `get_values()`. |
| `src/zlog/core/settings.py` | core | Add `"density": "default"` to `DEFAULTS`. |

## Architecture touch points

- **Threading:** none.
- **Model/proxy:** none — row height + delegate paint only; virtualization intact
  (heights come from `sizeHint`/`defaultSectionSize`, never a per-row widget).
- **Dependency direction:** `core/density.py` is Qt-free; `ui` imports it.

## Risks & regressions to check

- Wrap mode: `sizeHint` and the metadata band must use the *same* `row_pad` or
  the chip/first-line drift. Check with a wrapped long row at each density.
- Zoom interaction: height is `fm.height() + row_pad`, so density stacks
  cleanly on top of font-size changes.
- Settings drift guard: the `_settings_specs`↔`DEFAULTS` assert must still pass
  (add the key to both).

## Verification

- [ ] `uv run pytest` (add `tests/test_density.py` for `density_pad`).
- [ ] `uv run ruff check .` and `uv run ruff format --check .`
- [ ] `run-zlog` driver scenario `density-compact`: seed rows, set compact,
      screenshot shows tighter rows than `populated`.

## Open questions

- Exact pixel values (2/4/8) — tune against a screenshot; the map makes this a
  one-line change.
