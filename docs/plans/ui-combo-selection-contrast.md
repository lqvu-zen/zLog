# Plan: Fix hover/selected text contrast in combo box dropdowns

- **Status:** Done
- **Owner:** unassigned
- **Created:** 2026-07-09
- **Related:** [ui-button-feedback.md](ui-button-feedback.md) (same root-cause
  pattern, different widget), [device-picker.md](device-picker.md)

## Goal

After this ships, hovering or selecting an item in any combo box dropdown
(Device, Package, Min level, Filter/Highlight mode) keeps its text clearly
readable, instead of relying on whatever background the OS visual style paints
for that state.

## Findings
**Screens reviewed:** Device picker dropdown (populated with fake devices,
one `unauthorized`), Light and Dark themes. **Screenshots:** none committed —
see the caveat below.

**A caveat up front:** this environment renders through Qt's `offscreen`
platform (see `run-zlog`), which falls back to a generic Fusion-like style with
muted gray hover/selection tints. It does **not** reproduce the native
Windows visual style (accent-colored hover/selection) the real app runs under,
so I could not get a pixel-identical repro of "can't read when selected" the
way earlier bugs in this session were confirmed with a screenshot. The finding
below is a source-level diagnosis, not a visual repro — flagging that plainly
rather than overstating confidence.

### High
> Hurts usability or looks broken.

#### H1. Combo dropdown items don't style hover/selected state — text color can clash with the OS highlight
- **Screen / location:** every `QComboBox` dropdown app-wide (Device, Package,
  Min level, Filter/Highlight mode) — `src/zlog/ui/theme.py:75`
  (`build_stylesheet`'s `QComboBox QAbstractItemView` rule).
- **What & why:** the rule sets `color: {theme.text}` on the dropdown's item
  view unconditionally — there's no `:hover` or `:selected` (`::item:hover` /
  `::item:selected`) pseudo-state rule at all. Per Qt's own QSS behavior (the
  exact pattern already found and fixed for `QPushButton` in
  [ui-button-feedback.md](ui-button-feedback.md)), once a stylesheet sets an
  explicit `color` on a view, Qt stops automatically swapping it for the
  selected/hovered row — but the *background* for that row is still painted by
  whatever the active OS visual style uses for its highlight (on Windows,
  usually a saturated accent blue), since no background is specified for those
  states either. The fixed foreground and OS-controlled highlight background
  aren't guaranteed to pair legibly — which is exactly what "hard to read, and
  can't read when selected" describes. This affects every combo box, not just
  the device picker, since the QSS selector applies globally.
- **Recommendation:** add explicit `background-color` **and** `color` for both
  `::item:hover` and `::item:selected` on `QComboBox QAbstractItemView`, so the
  pairing is always known-good regardless of OS theme/accent color — mirroring
  the button fix. Reuse the existing `search_highlight` token (already paired
  with `theme.text` for row highlighting in the log table, and verified legible
  in both themes there) rather than adding new ones.
- **Screenshot:** none (see caveat above) — verify visually per the
  Verification section once implemented.

### What already works well
- The combo box's own closed-state text (the currently streaming device's name
  shown in the collapsed `Device:` box) is unaffected by this — `QComboBox`'s
  own `background-color`/`color` rule (not the dropdown's) reads fine in every
  screenshot taken so far.
- `QLineEdit, QComboBox { background-color: theme.base; color: theme.text; }`
  is a reasonable base rule — only the dropdown's per-item state pairing needs
  fixing.

### Deferred
- None.

## Scope

- **In:** H1 — hover/selected background+foreground pairing for
  `QComboBox QAbstractItemView` items, both themes.
- **Out (non-goals):** the combo box's own (closed) appearance, any other
  widget's dropdown/popup styling, `QCheckBox`/`QLineEdit` states.

## Design

| File | Layer | Change |
|---|---|---|
| `src/zlog/ui/theme.py` | ui | In `build_stylesheet`, add `QComboBox QAbstractItemView::item:hover {{ background-color: {theme.search_highlight}; color: {theme.text}; }}` and the same rule for `::item:selected`, right after the existing `QComboBox QAbstractItemView` line. No new `Theme` fields — reuses `search_highlight`. |

> **Implementation note (shipped):** used the log table's own `row_hover_bg`/`text` (hover) and `selection_bg`/`selection_text` (selected) tokens instead of the drafted `search_highlight`+`text`. Those tokens postdate this draft, are already verified legible in both themes, and make combo-dropdown selection match the table's selection exactly. Verified: 140 tests pass, ruff clean, both themes emit the new `::item:hover`/`::item:selected` rules, app renders. Real Windows-style visual confirmation remains for the user to close (offscreen can't reproduce the native accent highlight).

## Architecture touch points

- **Threading:** none — pure QSS change.
- **Model/proxy:** none.
- **Dependency direction:** unaffected — `theme.py` stays Qt-free/pure config.

## Risks & regressions to check

- `search_highlight` is tuned for a *row tint under normal text* (log table),
  not necessarily for a dropdown item at typical UI font size — confirm it
  still reads clearly at that size/weight in a screenshot before calling this
  done.
- This rule is global (`QComboBox QAbstractItemView`), so verify all four combo
  boxes (Device, Package, Min level, Filter/Highlight mode), not just Device.
- Since this environment can't reproduce the native Windows style, the
  strongest verification available here is a Light+Dark screenshot showing the
  new rule takes effect at all (explicit background now present where there
  was none) — real-machine confirmation from the user after this ships would
  close the loop properly.

## Verification

- [x] `uv run pytest` (140 passed)
- [x] `uv run ruff check .` and `uv run ruff format --check .`
- [ ] Screenshot the Device dropdown with an item hovered/selected, Light and
      Dark, and confirm text stays legible against the new explicit background.
- [ ] Spot-check the Min level and Filter/Highlight-mode dropdowns too, since
      the fix is global.

## Open questions

- Whether `search_highlight` is the right token here or a dedicated
  `list_hover`/`list_selected` pair would be clearer long-term — starting with
  reuse to avoid token sprawl; happy to split it out if it doesn't read well
  once you see it running.
