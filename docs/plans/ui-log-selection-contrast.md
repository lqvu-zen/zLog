# Plan: Fix unreadable log row text when selected or hovered

- **Status:** Done
- **Owner:** unassigned
- **Created:** 2026-07-09
- **Related:** [ui-button-feedback.md](ui-button-feedback.md),
  [ui-combo-selection-contrast.md](ui-combo-selection-contrast.md) (same
  root-cause pattern, different widgets)

## Goal

After this ships, selecting *or hovering* a log row keeps its text clearly
readable against the highlight, in both Light and Dark, instead of the text
nearly disappearing into it as reported.

## Amendment (2026-07-09, after selection fix shipped)
User confirmed the selection fix (H1 below) on real hardware, then reported a
second, related symptom: **hovering** a row (no click) also makes its text
unreadable. Adding `QTableView::item:selected` in the H1 fix very likely made
Qt start painting a native hover highlight on table rows that it either didn't
paint before, or painted differently — this offscreen environment doesn't
reproduce table-row hover at all (see H2 below), consistent with the same
native-style gap documented throughout this investigation. Same root cause,
same fix shape, added as H2 rather than a new plan since it's a direct
continuation of the same finding.

## Findings
**Screens reviewed:** log table with a row selected, both themes — user-
reported from the real running app (this session's own `run-zlog`/offscreen
screenshots did not reproduce it; see the caveat in
[ui-combo-selection-contrast.md](ui-combo-selection-contrast.md) about that
environment using a different visual style than the real app). Confirmed
directly with the user: selecting a row makes its **text nearly invisible
against the highlight**, in **both** Light and Dark.

### High
> Hurts usability or looks broken.

#### H1. Selected log rows have no explicit text/background pairing
- **Screen / location:** the log table, any row, once selected —
  `src/zlog/ui/theme.py:69-71` (`build_stylesheet`'s `QTableView` rule).
- **What & why:** `QTableView { background-color: theme.base; color: theme.text; ... }`
  sets the table's foreground unconditionally, and nothing in the stylesheet
  defines `QTableView::item:selected` (nor `selection-background-color` /
  `selection-color`). This is the same class of gap already found and fixed
  for `QPushButton` ([ui-button-feedback.md](ui-button-feedback.md)) and
  diagnosed for `QComboBox` dropdowns
  ([ui-combo-selection-contrast.md](ui-combo-selection-contrast.md)): without
  an explicit selected-state rule, whatever the active OS/Qt style paints for
  the selection background isn't guaranteed to pair legibly with our forced
  foreground color — and the user has now confirmed directly that in the real
  app (not just in theory) it doesn't: text is "nearly invisible against the
  highlight," in both themes. This hits the table hardest of the three,
  because clicking a row is the single most common interaction in the app —
  it drives the detail pane, bookmark toggling, and copy.
- **Recommendation:** add an explicit `QTableView::item:selected` rule with its
  own `background-color` and `color`, using two new `Theme` tokens
  (`selection_bg`, `selection_text`) rather than reusing `search_highlight` —
  unlike the combo dropdown, the table already uses `search_highlight` for a
  *different* meaning (highlight-mode search matches), and a selected row
  needs to stay visually distinct from a merely-matched row, especially since
  a row can be both at once.
- **Screenshot:** none from this environment (see caveat) — the user's own
  report is the evidence here; verify with a screenshot after the fix per
  Verification below, and ask the user to confirm on their machine since this
  environment couldn't reproduce the original bug either.

#### H2. Hovered log rows have the same gap (found after H1 shipped)
- **Screen / location:** the log table, any row, on mouse hover (no click) —
  same rule site, `src/zlog/ui/theme.py` (`QTableView` block).
- **What & why:** exactly the same mechanism as H1, just for `:hover` instead
  of `:selected` — no `QTableView::item:hover` rule exists, so a hovered row's
  background comes entirely from the active OS style with no guarantee it
  pairs legibly with the forced `theme.text` foreground. Confirmed by the user
  directly on real hardware. A local repro attempt (`QTest.mouseMove` over a
  row, offscreen platform) showed **no** hover highlight at all — consistent
  with this environment's style not matching the native one, the same caveat
  that applied to H1 before it shipped.
- **Recommendation:** add `QTableView::item:hover` with its own explicit
  `background-color`/`color` pairing, using a new, subtler token
  (`row_hover_bg`) than the stronger `selection_bg`, so hover and selection
  stay visually distinct — and order the `:hover` rule *before* `:selected` in
  the stylesheet text so a row that's both (cursor resting on the already-
  selected row) renders as selected, not a blend.
- **Screenshot:** none (see H1 caveat — same limitation applies).

### What already works well
- Row-level tinting (Warning/Error/Fatal backgrounds) and the bookmark marker
  are unaffected by this — only the selected-state pairing is missing.
- The detail pane correctly mirrors whatever row is current, so once selection
  is readable again, the rest of that flow (click → detail pane updates)
  doesn't need any change.

### Deferred
- Text selection *within* the detail pane (`QPlainTextEdit`, e.g. drag-
  selecting a word) uses the same unconditional `QWidget { color: theme.text }`
  base rule and could have a latent version of this same gap — not reported,
  not verified, out of scope here. Worth a quick look if it turns out to have
  the same problem.

## Scope

- **In:** H1 (shipped) — `QTableView::item:selected` pairing. H2 (this
  amendment) — `QTableView::item:hover` pairing, both themes.
- **Out (non-goals):** `QPlainTextEdit` text-selection contrast (see
  Deferred), the combo-box dropdown issue (tracked separately in
  [ui-combo-selection-contrast.md](ui-combo-selection-contrast.md)), row-level
  tint colors, bookmark color.

## Design

| File | Layer | Change |
|---|---|---|
| `src/zlog/ui/theme.py` | ui | *(H1, shipped)* Added `selection_bg`/`selection_text` fields and `QTableView::item:selected`. |
| `src/zlog/ui/theme.py` | ui | *(H2)* Add a `row_hover_bg` field to `Theme`. Light: `"#dbe9fb"` (pale blue-gray, distinct from `alt_base`/`header` and softer than `selection_bg`). Dark: `"#37475c"` (muted blue-gray, between `alt_base` and `selection_bg`). |
| `src/zlog/ui/theme.py` | ui | *(H2)* In `build_stylesheet`, add `QTableView::item:hover {{ background-color: {row_hover_bg}; color: {text}; }}` **before** the existing `::item:selected` rule (source order: later rule wins when both pseudo-states match the same row, so hovering the selected row still reads as selected). |

## Architecture touch points

- **Threading:** none — pure QSS change.
- **Model/proxy:** none — `LogTableModel`'s `BackgroundRole`/bookmark
  `DecorationRole` logic (`ui/log_model.py`) is untouched; Qt paints the
  selection state on top of (not blended with) the model-provided background,
  same as before.
- **Dependency direction:** unaffected — `theme.py` stays Qt-free/pure config.

## Risks & regressions to check

- A selected row that's *also* highlight-mode matched or level-tinted should
  show the selection color (not a muddy blend) — confirm in a screenshot for
  at least one Warning/Error row selected.
- A selected row that's *also* bookmarked must keep the bookmark marker
  visible against the new selection background (this exact combination was
  checked for the button/combo fixes' sibling bug — recheck here too).
- Multi-row selection (Ctrl+A / Select All, used by Copy) should look
  consistent across all selected rows, not just a single click.
- This environment's `run-zlog` screenshots render via the offscreen platform,
  which didn't reproduce the original bug — so a clean screenshot here is
  necessary but not sufficient proof; ask the user to confirm on their real
  Windows session before marking this fully resolved.
- (H2) Hovering the currently-selected row must still read as selected, not a
  hover/selection blend — this is why the rule order matters (see Design).
- (H2) Hover must not fight with `Follow`/autoscroll: since hover is purely a
  paint-time style state (not a model/selection change), it can't affect
  scrolling or the model — confirm nothing in `main_window.py` reacts to
  hover, only to real selection/current-index changes.

## Verification

- [x] `uv run pytest` — 113 passed (added `test_selection_colors_are_hex_and_styled`)
- [x] `uv run ruff check .` and `uv run ruff format --check .` — clean
- [x] Screenshotted a selected Error row (`details.png`) and a selected
      bookmarked Warning row (`bookmarks.png`) in Light: both show a solid
      blue background with crisp white text, fully replacing the level tint
      (no muddy blend), and the bookmark marker stays visible against it.
- [x] Screenshotted Select All (`copy.png`): all selected rows, including the
      blank banner row, are uniformly legible.
- [x] Screenshotted a selected Error row in Dark (`dark_selection.png`, ad hoc):
      same clean solid-blue/white-text result, previously-red tint fully
      replaced.
- [x] User confirmed on their real machine: selected rows are now clearly
      readable.
- [x] (H2) `uv run pytest` (114 passed, added
      `test_row_hover_is_hex_and_styled_before_selected`) / ruff — clean.
- [x] (H2) Confirmed the generated QSS contains `QTableView::item:hover`
      *before* `::item:selected` (source order), with the new `row_hover_bg`
      value present — this environment still can't render the actual hover
      paint (see caveat).
- [x] (H2) Re-shot `populated`/`details`/`dark`/`bookmarks`: no layout or
      selection regressions from adding the hover rule.
- [x] (H2) User confirmed on their real machine: hovering a row is now clearly
      readable in both themes, and hovering the selected row still looks
      selected.

## Open questions

- Exact `selection_bg` shades above are a reasonable starting guess (a
  standard accent blue, distinct from every other blue already in the
  palette), not final — happy to adjust once you've seen it on your machine.
