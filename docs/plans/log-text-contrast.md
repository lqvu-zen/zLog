# Plan: Make log metadata legible (contrast fix)

- **Status:** Done
- **Owner:** unassigned
- **Created:** 2026-07-09
- **Related:** [ui-combo-selection-contrast.md](ui-combo-selection-contrast.md),
  [logcat-style-ui.md](logcat-style-ui.md)

## Goal

After this ships, the time / pid-tid / tag columns on every log line are
comfortably readable (not faint gray), and the level chip stays visible on
selected rows in both themes.

## Findings (from a user screenshot, Light theme)

1. **Metadata columns are too faint.** `LogItemDelegate` paints the
   time / pid-tid / tag prefix with `theme.muted` (`#9aa0a6`). On white that is
   ~2.3:1 contrast — below WCAG AA (4.5:1) — so the whole left half of each line
   reads as pale gray. `muted` is meant for *disabled/secondary* chrome, not the
   metadata shown on every row.
2. **Level chip vanishes on selected rows.** In `paint`, the chip is filled with
   `base_fg if selected else lvl_color`; on a selected row `base_fg` is the white
   selection text, and the letter is also drawn white (`_chip_fg`) → white-on-white,
   invisible. Visible in the selected blue block in the screenshot.

## Scope

- **In:** a dedicated `meta_text` theme token (darker than `muted`) used by the
  delegate for the non-selected metadata columns; always paint the level chip in
  its level color so it stays visible when selected.
- **Out:** message per-level text colors (already readable), the query/device
  bars, combo dropdowns (covered by ui-combo-selection-contrast).

## Design

| File | Layer | Change |
|---|---|---|
| `src/zlog/ui/theme.py` | ui | Add `meta_text: str` to `Theme`; Light `#5f6368` (~5.9:1 on white), Dark `#b7bcc2`. Pure config, still Qt-free. |
| `src/zlog/ui/log_delegate.py` | ui | `set_theme` gains a `meta` arg → `self._meta`; `base_fg = _sel_fg if selected else _meta`. Fill the chip with `lvl_color` unconditionally (drop the `base_fg if selected` branch) so it never goes white-on-white. |
| `src/zlog/ui/main_window.py` | ui | Pass `theme.meta_text` into `log_delegate.set_theme(...)`. |

## Architecture touch points

- **Threading / model / proxy:** none — paint-only + one config field.
- **Dependency direction:** unaffected; `theme.py` stays pure.

## Risks & regressions to check

- Dark theme: `meta_text` must stay readable on `base` `#252526` without
  competing with the message — `#b7bcc2` is a mid-light gray, check it doesn't
  look like primary text.
- Selected rows: colored chip now sits on the blue selection bg — confirm the
  chip + white letter still reads (level colors are saturated, should be fine).

## Verification

- [ ] `uv run pytest`
- [ ] `uv run ruff check .` and `uv run ruff format --check .`
- [ ] Delegate unit check: metadata pen uses `meta_text` when unselected,
      `selection_text` when selected; chip fill == level color in both states.
- [ ] Screenshot Light + Dark, confirm time/pid/tag are clearly darker and the
      chip is visible on a selected row.
