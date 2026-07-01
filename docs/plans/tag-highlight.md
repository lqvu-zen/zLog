# Plan: Per-tag highlight colors

- **Status:** Done  <!-- Draft | Approved | In progress | Done | Abandoned -->
- **Owner:** Vũ
- **Created:** 2026-07-01

## Goal

Let the user assign a background color to a specific tag so all its rows stand out
in the stream — handy for watching one noisy component (e.g. tint every
`ActivityManager` row).

## Scope

- **In:**
  - Right-click a row → **Highlight tag '<tag>'…** opens a color picker; chosen color
    tints every row with that tag.
  - Right-click → **Clear tag highlights** removes them all.
  - A highlighted tag's color takes precedence over the level tint.
- **Out (non-goals):**
  - Persisting highlights across launches (needs a settings file — future).
  - Highlighting by regex/message (tag-only for v1); per-tag *text* color or bold.
  - A full manager dialog (add via right-click is enough for v1).

## Design

The row-tint source already lives in the model; we add a second, higher-priority
map keyed by tag. The picker and menu are UI glue.

| File | Layer | Change |
|---|---|---|
| `src/zlog/ui/log_model.py` | ui | `LogTableModel` gains `_tag_colors: dict[str, QColor]`, `set_tag_color(tag, hex)`, and `clear_tag_colors()`. In `data()` `BackgroundRole`, return the tag color if the entry's tag has one, else the level tint (tag wins). |
| `src/zlog/ui/main_window.py` | ui | Switch the table's context menu from `ActionsContextMenu` to a `customContextMenuRequested` handler that builds a `QMenu` with the existing **Copy** / **Select All** actions plus **Highlight tag '<tag>'…** (opens `QColorDialog`; applies via `model.set_tag_color`) and **Clear tag highlights** (`model.clear_tag_colors`). The tag comes from the row under the cursor. |
| `.claude/skills/run-zlog/scripts/driver.py` | (skill) | a `highlight` scenario: seed rows, `model.set_tag_color("Choreographer", "#b3e5fc")`, screenshot to show the tinted rows overriding the level tint. |

## Architecture touch points

- **Threading/model:** none new. The tag-color lookup is O(1) in `data()`; the model
  stays virtualized. A highlight change repaints via `viewport().update()` (or a
  targeted `dataChanged`) — no reset.
- **Colors:** user-chosen highlight colors come from `QColorDialog`, so they're not
  theme tokens (that's expected — they're per-session user choices). The default
  level tints still come from `ui/theme.py`.
- **Dependency direction:** UI-only; `core` untouched, still Qt-free.
- **Versioning:** no bump (release-only).

## Risks & regressions to check

- A tag highlight visibly overrides the level tint for those rows; other rows keep
  their level tint.
- Clearing highlights restores level tints everywhere.
- The context menu still offers Copy / Select All (don't regress the copy feature).
- Right-clicking an unparsed/banner row (empty tag) degrades gracefully (the
  Highlight item is disabled or a no-op).
- Readability is the user's responsibility (their color choice), but the app
  shouldn't crash on any picked color.

## Verification

- [x] `uv run pytest` (unchanged; still green)
- [x] `uv run ruff check .` and `uv run ruff format --check .`
- [x] `run-zlog` `highlight` screenshot shows a tag's rows tinted over the level color
- [ ] Manual: right-click a row → Highlight → pick a color → those rows tint; Clear
      removes them; Copy / Select All still work

## Open questions

- Highlight the **whole row background** (proposed) vs only the Tag cell?
- Offer a small set of preset colors in the menu for one-click, in addition to the
  full color picker?
