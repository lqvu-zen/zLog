# Plan: Merge device + package controls into one bar

- **Status:** Done
- **Owner:** unassigned
- **Created:** 2026-07-10
- **Related:** [two-bar-header.md](two-bar-header.md) (split them apart earlier),
  [package-bar.md](package-bar.md)

## Goal

After this ships, the device/stream controls and the package controls share a
single toolbar row, visually separated by a vertical divider, with the query box
still on its own full-width row below. One fewer stacked row above the log.

## Why

The user notes there's horizontal room to combine them. Two near-empty rows waste
vertical space that could go to the log. A `QFrame` VLine divider keeps the two
groups readable as distinct clusters. The `_vsep()` helper already exists (added
but currently unused) for exactly this.

## Scope

- **In:** collapse `device_row` and `package_row` into one `top_row`, with
  `self._vsep()` (plus small spacing) between the device group and the package
  group; a single trailing stretch.
- **Out:** the filter/query row (stays separate, full width), any widget behavior,
  the menus.

## Design

| File | Layer | Change |
|---|---|---|
| `src/zlog/ui/main_window.py` | ui | In `_build_layout`, replace the two `QHBoxLayout`s with one `top_row`: Device label/combo/refresh · stream buttons (▶ ■ ✕ Clear device Follow) · jump buttons · `addSpacing(12)` + `_vsep()` + `addSpacing(12)` · Package label/combo/Load/Apply/Clear pkg · `addStretch(1)`. Add just `top_row` to the outer `QVBoxLayout` (drop the second `addLayout`). |

## Architecture touch points

- **Threading / model / proxy:** none — pure layout.
- **Widgets unchanged:** same widget instances, same signals; only their container
  layout changes, so every existing behavior and test keeps working.

## Risks & regressions to check

- **Narrow windows:** combined row is wide (two comboboxes + ~9 buttons). On a
  small window the comboboxes hold their min width and the row may clip before the
  stretch; acceptable since the default window is 1100px and it's resizable. Note
  if it looks cramped in the screenshot.
- **Divider rendering:** `_vsep()` is a sunken VLine; confirm it shows between the
  groups and not at a row edge.

## Verification

- [ ] `uv run pytest` (layout-only; existing window tests must still pass)
- [ ] `uv run ruff check .` and `uv run ruff format --check .`
- [ ] Screenshot the header: one control row with a divider between device and
      package groups, query row below.
