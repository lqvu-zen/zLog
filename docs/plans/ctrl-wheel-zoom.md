# Plan: Ctrl + mouse wheel to zoom text

- **Status:** Done
- **Owner:** unassigned
- **Created:** 2026-07-10
- **Related:** [font-zoom.md](font-zoom.md) (added the zoom + Ctrl+=/-/0 shortcuts)

## Goal

After this ships, holding Ctrl and scrolling the wheel over the log list or the
detail pane zooms the text in/out — the same effect as Ctrl+= / Ctrl+- — while a
plain wheel keeps scrolling as normal.

## Why

Ctrl+scroll is the muscle-memory zoom gesture (editors, browsers). It reuses the
existing `_zoom()` (clamped to font_delta ∈ [-4, 12]) and persistence, so it's a
thin input layer over logic that already works.

## Scope

- **In:** intercept Ctrl+Wheel over `self.table` and `self.detail` viewports and
  call `_zoom(±1)`; consume the event so it doesn't also scroll (and so
  `QPlainTextEdit`'s built-in Ctrl-wheel zoom can't desync from `font_delta`).
- **Out:** horizontal-wheel handling, per-notch multi-step zoom, changing the
  menu items or shortcuts.

## Design

| File | Layer | Change |
|---|---|---|
| `src/zlog/ui/main_window.py` | ui | Import `QEvent`. Install `self` as an event filter on `self.table.viewport()` and `self.detail.viewport()` in `_connect_signals`. Add `eventFilter(obj, event)`: on `QEvent.Wheel` with `Qt.ControlModifier`, call `self._zoom(1 if angleDelta().y() > 0 else -1)` and return `True`; otherwise defer to `super().eventFilter`. |
| `tests/test_main_window_settings.py` | tests | Ctrl+Wheel up over the table increments `font_delta` and is consumed (returns True); Ctrl+Wheel down over the detail viewport decrements it; a plain wheel (no Ctrl) is not consumed and leaves `font_delta` unchanged. |

## Architecture touch points

- **Threading / model / proxy:** none — input handling only.
- **Reuses `_zoom`/`_apply_font`:** clamping, both-pane font sync, and the
  `font_delta` setting persistence all keep working unchanged.

## Risks & regressions to check

- **Don't eat plain scrolling:** only consume when Ctrl is held; return the base
  result otherwise so normal wheel-scroll still works.
- **QPlainTextEdit built-in zoom:** intercepting Ctrl+Wheel on the detail viewport
  prevents its native zoomIn/out from fighting `_apply_font`.
- **angleDelta sign:** natural/inverted wheels — use the sign of `.y()`; zero delta
  is a no-op.

## Verification

- [ ] `uv run pytest` (new event-filter tests)
- [ ] `uv run ruff check .` and `uv run ruff format --check .`
- [ ] Manual: Ctrl+scroll over the log grows/shrinks text; plain scroll still
      scrolls; Ctrl+0 still resets.
