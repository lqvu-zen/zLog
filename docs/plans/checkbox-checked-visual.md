# Plan: Make the checked state of checkboxes visible

- **Status:** Done
- **Owner:** unassigned
- **Created:** 2026-07-11
- **Related:** [ui-combo-selection-contrast.md](ui-combo-selection-contrast.md),
  [ui-button-feedback.md](ui-button-feedback.md) (same "QSS on a sub-control
  disables native rendering" root cause)

## Goal

The Follow (and any) checkbox visibly shows checked vs unchecked.

## Findings (bug report: "I click Follow but it still looks unchecked")

`build_stylesheet` styled `QCheckBox::indicator` with only a border. In Qt, once a
stylesheet touches the indicator, Qt stops drawing its native check glyph — so
checked and unchecked both render as the same empty bordered box. The toggle
worked (state flipped, tailing logic correct); it just never *looked* checked.

## Change

`src/zlog/ui/theme.py` — give `QCheckBox::indicator` an explicit size + bordered
box for the unchecked state and a `:checked` rule that fills the box with
`theme.selection_bg` (the accent), so checked is unmistakable in both themes.
`tests/test_theme.py` — assert the stylesheet includes `QCheckBox::indicator:checked`
and the accent fill for both themes.

## Verification

- [x] `uv run pytest` (154 passed)
- [x] `uv run ruff check .` / `format --check .`
- [x] Screenshot: Follow shows a filled accent box when checked, empty when not.
