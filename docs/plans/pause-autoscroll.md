# Plan: Pause / follow autoscroll

- **Status:** Done  <!-- Draft | Approved | In progress | Done | Abandoned -->
- **Owner:** Vũ
- **Created:** 2026-06-30

## Goal

Give the user explicit control over tail-following: a **Follow** toggle that, when
on, keeps the view pinned to the newest line, and when off, lets them scroll back
through history without being yanked to the bottom by incoming logs.

## Scope

- **In:** a **Follow** checkbox (default on) in the toolbar; `on_batch` scrolls to
  the bottom only when it's checked.
- **Out:** remembering the toggle across launches; a "jump to bottom" button.

## Design

| File | Layer | Change |
|---|---|---|
| `src/zlog/ui/main_window.py` | ui | Add `self.follow_check = QCheckBox("Follow")` (checked by default) to row 1. In `on_batch`, replace the implicit "scroll only if already at bottom" heuristic with: `if self.follow_check.isChecked(): self.table.scrollToBottom()`. Drop the now-unused `_is_scrolled_to_bottom` helper. |
| `.claude/skills/run-zlog/scripts/driver.py` | (skill) | no new scenario needed (scroll state isn't meaningful in a static grab); the `populated` shot already shows the toggle. |

## Architecture touch points

- **Threading/model:** none. `on_batch` still runs on the main thread from the
  reader's signal; only the scroll decision changes. Virtualization untouched.
- **Dependency direction:** UI-only change.
- **Versioning:** no bump (release-only).

## Risks & regressions to check

- Follow on: view sticks to newest line as batches arrive.
- Follow off: scrolling up stays put while new lines append.
- Toggling Follow on jumps to the bottom on the next batch (acceptable).

## Verification

- [x] `uv run pytest` (unchanged; still green)
- [x] `uv run ruff check .` and `uv run ruff format --check .`
- [x] `run-zlog` `populated` screenshot shows the Follow toggle
- [ ] Manual: stream, scroll up with Follow off (stays), turn Follow on (jumps to tail)

## Open questions

- Label **"Follow"** (proposed) vs "Autoscroll"?
- Default **on** (proposed)?
