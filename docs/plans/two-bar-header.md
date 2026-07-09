# Plan: Device bar + dedicated filter row

- **Status:** Done
- **Owner:** Vũ
- **Created:** 2026-07-09
- **Related:** logcat-style-ui.md, menu-bar.md

## Goal

Put device selection and the stream/device controls together on one horizontal
**device bar**, and give the **query/filter box its own full-width row** below it.
Drop the left vertical icon rail.

## Scope

- **In:** `_build_layout` — a device row (`Device:` + combo + ↻ ▶ ■ ✕ Follow ⭱ ⭳),
  then a filter row with just the query bar, then the splitter. Remove the rail.
- **Out:** widget behavior, menus, the log view (unchanged).

## Design

| File | Change |
|---|---|
| `src/zlog/ui/main_window.py` | Rewrite `_build_layout`: device controls move from the vertical rail into a horizontal device bar; the query bar sits alone on the next row. Same widgets/wiring. |

## Verification

- [ ] `uv run pytest` / ruff (behavior unchanged)
- [ ] Headless screenshot shows a device bar over a full-width filter row
