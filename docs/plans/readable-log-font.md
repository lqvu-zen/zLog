# Plan: A readable log font

- **Status:** Done
- **Owner:** unassigned
- **Created:** 2026-07-10
- **Related:** [font-zoom.md](font-zoom.md), [ctrl-wheel-zoom.md](ctrl-wheel-zoom.md)

## Goal

After this ships, the log reads clearly out of the box: a modern, high-legibility
monospace face at a comfortable default size, still adjustable via Ctrl+=/- and
Ctrl+scroll.

## Why (bug report: "the current font is hard to read")

`QFont("monospace")` is not a real family on Windows, so Qt falls back to a thin
Courier-style face; and the base size is taken from the app default (~9pt), which
is small. Both hurt legibility. Naming actual, widely-available monospace families
and setting a sane base point size fixes it without removing the zoom controls.

## Scope

- **In:** a preferred monospace family chain for the log view and a fixed, readable
  base point size that the zoom offset (`font_delta`) still adjusts.
- **Out:** the detail pane's proportional font (fine as-is), a user-facing font
  picker, per-theme fonts.

## Design

| File | Layer | Change |
|---|---|---|
| `src/zlog/ui/main_window.py` | ui | Add module constants `LOG_FONT_FAMILIES = ["Consolas", "Cascadia Mono", "SF Mono", "Menlo", "DejaVu Sans Mono", "Courier New"]` and `BASE_FONT_PT = 11`. In `_build_widgets`, build the log font with `setFamilies(LOG_FONT_FAMILIES)`, `setStyleHint(QFont.Monospace)`, `setFixedPitch(True)`. In `_apply_font`, compute `size` from `BASE_FONT_PT + self._font_delta` (drop the tiny app-default base). |
| `tests/test_main_window_settings.py` | tests | The log font is monospace-hinted and its point size is the readable base (11) at zero zoom; zoom still shifts it. |

## Architecture touch points

- **theme.py stays Qt-free:** font choice lives in the ui layer (needs `QFont`),
  not in the pure theme config.
- **Zoom unchanged:** `font_delta` persistence and clamping keep working; only the
  base the offset is added to changes (app-default → fixed 11pt).

## Risks & regressions to check

- **Family availability:** the first present family wins (Consolas on Windows,
  DejaVu Sans Mono on the Linux CI); `Courier New` + the Monospace style hint are
  the last-resort fallbacks, so it degrades safely.
- **Row height:** `_apply_font` already resizes rows from `QFontMetrics`, so a
  larger base reflows row height correctly.
- **Existing zoom test:** still valid — it drives `_zoom`/`_reset_zoom`, which now
  build on the 11pt base.

## Verification

- [ ] `uv run pytest`
- [ ] `uv run ruff check .` and `uv run ruff format --check .`
- [ ] Screenshot: log text is clearly a rounded, readable monospace at a
      comfortable size.
