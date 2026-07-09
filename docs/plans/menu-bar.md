# Plan: Restore the File / View menu bar

- **Status:** Done
- **Owner:** Vũ
- **Created:** 2026-07-09
- **Related:** logcat-style-ui.md (moved these into the ⋮ overflow)

## Goal

Keep **File** and **View** as a normal menu bar across the top, instead of tucking
them behind the ⋮ overflow button. Everyday actions stay one click away.

## Scope

- **In:** build the File/View menus on `self.menuBar()`; remove the ⋮ `overflow_btn`
  from the top query row and its creation/wiring.
- **Out:** menu contents (unchanged); the icon rail and query bar (unchanged).

## Design

| File | Change |
|---|---|
| `src/zlog/ui/main_window.py` | `_build_menus` creates `file_menu`/`view_menu` on `self.menuBar()` (drop `self._overflow_menu`); remove `overflow_btn` from `_build_widgets` and `_build_layout`. |

## Risks & regressions to check

- Every menu action still present and wired (themes, save/open, zoom, bookmarks,
  presets, search options, clear filters).
- Top row is now just Device + query bar; window still lays out cleanly.

## Verification

- [ ] `uv run pytest` / ruff
- [ ] Headless screenshot shows a top menu bar with File and View
