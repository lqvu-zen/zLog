# Plan: UI review polish (Message header alignment, bookmark/checkbox contrast)

- **Status:** Draft
- **Owner:** unassigned
- **Created:** 2026-07-08
- **Related:** [toolbar-tidy.md](toolbar-tidy.md), [theming-dark-mode.md](theming-dark-mode.md)

## Goal

After this ships, the Message column header lines up with its left-aligned data,
and bookmark/checkbox affordances read clearly at a glance in both themes — none
of the three fixes change behavior, only how existing state is rendered.

## Findings
**Screens reviewed:** idle/empty, populated, filtered (Warning+), Dark theme,
bookmarks, match navigation (filter mode), highlight mode, column visibility,
detail pane, device picker, package filter, regex search, opened-from-file,
no-match, copy/select-all, streaming status guide.
**Screenshots:** `smoke-idle.png`, `populated.png`, `filtered-warn-and-above.png`,
`dark.png`, `bookmarks.png`, `match-nav.png`, `highlight.png`, `columns.png`,
`details.png`, `devices.png`, `package-filter.png`, `regex-search.png`,
`opened.png`, `no-match.png`, `copy.png`, `guide-streaming.png` (all in
`.claude/skills/run-zlog/screenshots/`).

### Medium
> Noticeable friction or inconsistency.

#### M1. Message column header doesn't align with its data
- **Screen / location:** every populated screen — `src/zlog/ui/main_window.py:97-104`
  (header section setup; no `setDefaultAlignment` call, so Qt's default centered
  horizontal-header alignment applies to every column).
- **What & why:** Time/PID/TID/Level/Tag are narrow enough that centered vs.
  left-aligned header text is indistinguishable. Message is wide and stretches
  (`QHeaderView.Stretch`), so its header label floats near the horizontal center of
  the column while every cell's text is left-aligned — see `populated.png`, where
  "Message" sits well right of where the message text actually starts. It's a
  small but constant visual disagreement between label and data on the column
  users scan most.
- **Recommendation:** `header.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)`
  in `_build_widgets`.
- **Screenshot:** `populated.png`

### Low
> Polish.

#### L1. Bookmark marker color is close to the Warning row tint
- **Screen / location:** `bookmarks.png` — `src/zlog/ui/theme.py:39,53` (`bookmark`
  token: `#f4b400` Light / `#e0a800` Dark, both warm amber).
- **What & why:** `level_colors["W"]` is also a pale amber (`#fff4c8` / `#4d4526`).
  On a bookmarked Warning-level row the marker swatch and the row tint are both in
  the amber family — still distinguishable (saturated square vs. pale background)
  but not a strongly distinct signal at a glance the way a contrasting hue would be.
- **Recommendation:** move `bookmark` to a hue outside the level-tint family (e.g. a
  blue or teal) so a bookmark reads unambiguously regardless of which level tints
  the row it sits on.

#### L2. Regex/Case checkbox indicators are low-contrast in Dark theme
- **Screen / location:** `dark.png` — `src/zlog/ui/theme.py` `build_stylesheet`
  (no `QCheckBox::indicator` rule; the unchecked box border falls back to the
  native style's default, which reads faint against `theme.window` = `#1e1e1e`).
- **What & why:** In Dark theme the empty checkbox outline for "Regex"/"Case" is
  hard to make out until you look closely, whereas in Light it's a clear box. Minor
  since checked-state still shows a checkmark, but affects scanability of active
  filter state.
- **Recommendation:** add a `QCheckBox::indicator { border: 1px solid <muted-or-brighter>; }`
  rule per theme in `build_stylesheet`, using a value with more separation from
  `theme.window`.

### What already works well
- **Contextual empty states** (`main_window.py:_update_placeholder`): "No logs
  yet…" before any capture vs. "No lines match the current filters." when a filter
  zeroes out the view (`empty.png`, `no-match.png`).
- **Selection, bookmark, and highlight-mode tints all stay legible** in both
  themes, including a bookmarked row that's also selected (`bookmarks.png`) — worth
  protecting if `theme.py` or the delegate ever changes.
- **Reserved-width match label** (`match_label.setMinimumWidth(64)`) keeps the
  search row from jittering as the match count text appears/disappears.
- **Toolbar's three-row split** (stream controls / scope / search) keeps the table
  dominant and each row legible.
- **Level tinting** stays consistent and readable across Light/Dark without
  relying on color alone (the Level letter column is always visible too).

### Deferred
- None — all findings from this pass are in scope below.

## Scope

- **In:**
  - **M1** — Message column header currently renders centered (Qt's default)
    while every Message cell is left-aligned, so the label visibly floats away
    from the data on the wide, stretched column.
  - **L1** — the bookmark marker color (`theme.bookmark`) is in the same warm/
    amber family as the Warning row tint (`level_colors["W"]`), so a bookmarked
    Warning row doesn't read as distinctly bookmarked as it should.
  - **L2** — in Dark theme, the unchecked Regex/Case checkbox indicator has very
    low contrast against the chrome background, making active-filter state hard
    to scan.
- **Out (non-goals):** any other finding from the 2026-07-08 review was already
  filed as "works well" — no other visual behavior changes. Not touching level
  colors, search-highlight color, or any other theme token beyond `bookmark` and
  the new checkbox-indicator rule.

## Design

| File | Layer | Change |
|---|---|---|
| `src/zlog/ui/main_window.py` | ui | In `_build_widgets`, after the existing per-column `setSectionResizeMode`/`setColumnWidth` loop, set the header's default alignment to left so Message (and every column) aligns with its left-aligned cell data: `header.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)`. |
| `src/zlog/ui/theme.py` | ui | Change `bookmark` on both `LIGHT` and `DARK` `Theme` instances to a hue outside the level-tint (amber/red) family — e.g. a blue/teal such as `#1a73e8` (Light) / `#4da3ff` (Dark) — chosen to stay clearly readable against `base`/`alt_base` and distinct from `level_colors["W"]`. |
| `src/zlog/ui/theme.py` | ui | In `build_stylesheet`, add a `QCheckBox::indicator { border: 1px solid <value>; }` rule per theme, using a border color with more separation from `theme.window` than the native default (e.g. `theme.muted` or a slightly lighter/darker variant), so the unchecked box is visible in Dark. |

## Architecture touch points

- **Threading:** none — pure rendering/style changes, no background work involved.
- **Model/proxy:** none — no new column, no new filter predicate. `LogTableModel`'s
  `Qt.DecorationRole` bookmark handling (`ui/log_model.py`) is unchanged; only the
  color it's given by `theme.py` changes.
- **Dependency direction:** unaffected — `theme.py` stays Qt-free/pure config;
  `main_window.py` and `log_model.py` keep consuming it the same way.

## Risks & regressions to check

- Changing `header.setDefaultAlignment` applies to *all* columns, not just
  Message — confirm Time/PID/TID/Level/Tag still read fine left-aligned (they're
  narrow enough that this should be a non-issue, but verify in a screenshot).
- The new `bookmark` color must stay legible tinted over every row background it
  can appear on: default (white/`alt_base`), and all three level tints (W/E/F), in
  both Light and Dark — check all six combinations don't wash out.
- `QCheckBox::indicator` styling can be a rabbit hole in Qt (checked-state,
  hover, disabled sub-states) — keep the rule minimal (border color only) so
  Follow/Regex/Case/column-visibility checkboxes elsewhere don't regress.
- Re-verify bookmarked + selected row (the combination the original review
  screenshot exercised) still has good contrast after the color change.

## Verification

- [ ] `uv run pytest`
- [ ] `uv run ruff check .` and `uv run ruff format --check .`
- [ ] Re-run `run-zlog` scenarios `populated`, `bookmarks`, `dark`, and a new
      Dark+bookmarks combination; confirm in the screenshots that:
      - Message header text starts at the same x-position as message cell text.
      - The bookmark swatch is visibly distinct from the W/E/F row tints.
      - Regex/Case checkbox outlines are visible, unchecked, in Dark.

## Open questions

- Exact replacement hue for `bookmark` — blue/teal proposed above is a starting
  point, not final; confirm against both themes' full palette before committing.
