# Plan: Font zoom (readability)

- **Status:** Done
- **Owner:** Vũ
- **Created:** 2026-07-08
- **Related:** settings-persistence, detail-pane

## Goal

Zoom the log table and detail pane text in/out (Ctrl+= / Ctrl+- / Ctrl+0) so dense
logcat output is comfortable to read; the zoom level persists across launches.

## Scope

- **In:** View → Zoom In / Zoom Out / Reset, with Ctrl+= / Ctrl+- / Ctrl+0; a font
  size delta applied to the table and detail pane; persisted as `font_delta`.
- **Out:** per-widget fonts; a monospace toggle (possible follow-up); changing menu/
  toolbar fonts.

## Design

| File | Layer | Change |
|---|---|---|
| `src/zlog/core/settings.py` | core | Add `"font_delta": 0` to `DEFAULTS`. |
| `src/zlog/ui/main_window.py` | ui | Track `self._font_delta`; `_apply_font()` sets point size (base + delta, clamped) on `table` and `detail`; `_zoom(step)` / reset; View menu items + shortcuts; a `font_delta` settings spec row. |

## Architecture touch points

- Pure presentation; no model/proxy/threading change. Font applies to whole widgets,
  so the virtualized table still renders cheaply.
- Versioning: no bump.

## Risks & regressions to check

- Clamp so the font never becomes unreadably small/huge.
- `font_delta` round-trips through settings; spec-parity assert holds.

## Verification

- [ ] `uv run pytest` (headless: zoom changes the table font size; round-trip)
- [ ] `uv run ruff check .` and `uv run ruff format --check .`
