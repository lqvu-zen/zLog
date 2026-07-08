# Plan: Button click/hover feedback

- **Status:** Done
- **Owner:** unassigned
- **Created:** 2026-07-08
- **Related:** [ui-review-polish.md](ui-review-polish.md), [toolbar-tidy.md](toolbar-tidy.md)

## Goal

After this ships, pressing or hovering any button in zLog (Start/Stop/Clear,
Refresh, Load/Apply/Clear pkg, Top/Latest, the `<`/`>` match-nav buttons, Clear
filters) visibly changes its appearance, so clicking feels responsive instead of
silent.

## Findings
**Screens reviewed:** toolbar (all three rows) in idle state, Light and Dark
themes. **Screenshots:** `btn_normal.png`, `btn_pressed.png`, `btn_hover.png`
(scratch — reproduced via `button.setDown(True)` and a synthetic `QEvent.Enter`,
not yet committed under `run-zlog/screenshots/`; see Verification).

### High
> Hurts usability or looks broken.

#### H1. Buttons give no visual feedback on hover or press
- **Screen / location:** every toolbar button, all three rows —
  `src/zlog/ui/theme.py:70-72` (`build_stylesheet`'s `QPushButton` rule).
- **What & why:** `QPushButton` is styled with an explicit `background-color`,
  `border`, and `padding`, and only a `:disabled` state is defined — no `:hover`
  or `:pressed` rule. Once a stylesheet sets `background-color` on a widget, Qt's
  native style stops varying it automatically for hover/pressed; without an
  explicit rule for those states, the button renders **identically** at rest,
  hovered, and pressed. Confirmed directly: grabbed the same button (`Refresh`)
  at rest, with `setDown(True)` (pressed), and after a synthetic `QEvent.Enter`
  (hover) — all three screenshots are pixel-identical. This is exactly what the
  user reported: clicking a button doesn't *feel* like it registered. It also
  means the `border: 1px solid {theme.header}` is the same color as the
  `background-color`, so buttons have no visible edge at rest either — they read
  as flat colored rectangles rather than clickable controls.
- **Recommendation:** add `:hover` and `:pressed` rules to the `QPushButton` QSS
  in `build_stylesheet`, using new `Theme` tokens (not ad hoc hex) so the palette
  stays centralized, and give the resting border a color distinct from the fill
  so buttons read as bordered controls even before interaction.
- **Screenshot:** `btn_normal.png` / `btn_pressed.png` / `btn_hover.png` (scratch)

### What already works well
- **Disabled buttons** (`Stop` when idle, package/level controls before a device
  is chosen) already dim via `QPushButton:disabled { color: theme.muted; }` —
  keep that rule; only the hover/pressed gap needs filling.
- **Button copy** is specific (Start/Stop/Clear/Refresh/Load/Apply/Clear pkg/Top/
  Latest/Clear filters) — nothing to rename here.

### Deferred
- Disabled buttons only dim their *text*, not their background — a real but
  smaller affordance gap than H1, and not what the user reported. Leaving it for
  a future pass unless you'd rather bundle it in here since the stylesheet block
  is already being touched.

## Scope

- **In:** H1 — add hover/pressed QSS states for `QPushButton`, plus a visible
  resting border, in both Light and Dark themes.
- **Out (non-goals):** disabled-button background (see Deferred), any other
  widget's hover/pressed state (QComboBox, QCheckBox, QLineEdit weren't reported
  and weren't part of this ask), button copy/layout.

## Design

| File | Layer | Change |
|---|---|---|
| `src/zlog/ui/theme.py` | ui | Add two fields to `Theme`: `button_hover` and `button_pressed` (hex). Light: `header="#e8e8e8"` → `button_hover="#dcdcdc"`, `button_pressed="#cfcfcf"`. Dark: `header="#333333"` → `button_hover="#3d3d3d"`, `button_pressed="#474747"`. |
| `src/zlog/ui/theme.py` | ui | In `build_stylesheet`'s `QPushButton` rule, change the border to a fixed, visible color (`theme.muted`) instead of matching the background, and add `QPushButton:hover { background-color: {button_hover}; }` and `QPushButton:pressed { background-color: {button_pressed}; }`. |

## Architecture touch points

- **Threading:** none — pure QSS/style change.
- **Model/proxy:** none.
- **Dependency direction:** unaffected — `theme.py` stays Qt-free/pure config.

## Risks & regressions to check

- `QPushButton:disabled` must still look clearly disabled — verify the new
  border color doesn't make a disabled button look enabled (Qt automatically
  dims a QSS-styled border/background somewhat for `:disabled`, but confirm in
  a screenshot rather than assume).
- The new border must stay legible against `theme.window` in both themes (not
  just against the button's own fill).
- Match-nav's narrow `<`/`>` buttons (`setMaximumWidth(28)`) shouldn't clip or
  look cramped with a border added where there previously was none.

## Verification

- [x] `uv run pytest` — 109 passed
- [x] `uv run ruff check .` and `uv run ruff format --check .` — clean
- [x] Verified rest/hover/pressed by pixel-sampling the Refresh button's fill in
      both themes (a synthetic `QEvent.Enter` turned out not to set Qt's
      internal hover state — `QTest.mouseMove` does): Light
      `#e8e8e8` → hover `#dcdcdc` → pressed `#cfcfcf`; Dark `#333333` → hover
      `#3d3d3d` → pressed `#474747`. All three now distinct in both themes.
- [x] Re-ran `smoke`, `populated`, `dark`, `match-nav`: the new border doesn't
      crowd or clip anything, including the narrow `<`/`>` match-nav buttons,
      and the disabled `Stop`/`Load`/`Apply` buttons still read as clearly
      disabled (dimmed text) next to enabled siblings.

## Open questions

- Exact hover/pressed shades above are a reasonable starting guess (small,
  even steps off `header`), not final — happy to nudge them once you see the
  screenshot.
