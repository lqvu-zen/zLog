# Plan: Jump to latest / top

- **Status:** Done
- **Owner:** Vũ
- **Created:** 2026-07-08
- **Related:** pause-autoscroll (Follow toggle)

## Goal

Two toolbar buttons (with shortcuts) to jump to the newest line or the top of the
log on demand, independent of the Follow toggle — so you can scroll freely in a big
log and snap back without re-enabling Follow.

## Scope

- **In:** a **⭱ Top** and **⭳ Latest** button on row 1; `scrollToTop()` /
  `scrollToBottom()` slots; shortcuts (Ctrl+Home / Ctrl+End). "Latest" scrolls to the
  bottom of the *filtered* view (proxy), not the master list.
- **Out:** changing Follow semantics, remembering scroll position across runs.

## Design

Pure `ui/` wiring; no core/model/proxy change.

| File | Layer | Change |
|---|---|---|
| `src/zlog/ui/main_window.py` | ui | Add `to_top_btn`/`to_latest_btn` in `_build_widgets`, place them in row 1, connect in `_connect_signals` to `self.table.scrollToTop` / `self.table.scrollToBottom`. |

## Architecture touch points

- No threading/model/proxy semantics change; buttons just move the viewport.
- Follow still auto-scrolls on new batches; these are manual, one-shot jumps.
- Versioning: no bump.

## Risks & regressions to check

- Empty log: buttons are harmless no-ops.
- With Follow on, "Top" scrolls up but the next batch snaps back to bottom (expected).

## Verification

- [ ] `uv run pytest`
- [ ] `uv run ruff check .` and `uv run ruff format --check .`
- [ ] Headless: append rows, call scroll slots, assert no error; screenshot shows buttons
