# Plan: Mute tag / PID from the context menu

- **Status:** Draft
- **Owner:** Vũ
- **Created:** 2026-07-08
- **Related:** exclude-filter, tag-highlight

## Goal

Right-click a row → "Mute tag X" (or "Mute PID") to quickly add it to the exclude
filter, so noisy sources can be silenced in one click.

## Scope

- **In:** context-menu items that append the row's tag (or PID) to the Exclude field
  as a regex alternation, and an "Unmute all" that clears exclude.
- **Out:** a managed mute list UI; persisting mutes separately from the exclude text.

## Design

| File | Layer | Change |
|---|---|---|
| `src/zlog/ui/main_window.py` | ui | In `_show_table_menu`, add "Mute tag {tag}"; `_mute_tag(tag)` ORs `\btag\b` into the exclude field (enabling Regex) and re-applies. |

## Architecture touch points

- Reuses the exclude proxy gate; no core/model change. Enables the Regex toggle so the
  alternation matches.
- Versioning: no bump.

## Risks & regressions to check

- Escaping the tag for regex; combining with an existing exclude term.
- Unmute clears exclude without touching search.

## Verification

- [ ] `uv run pytest` (headless: mute appends and hides that tag's rows)
- [ ] `uv run ruff check .` and `uv run ruff format --check .`
