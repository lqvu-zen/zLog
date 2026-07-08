# Plan: Toolbar tidy-up (two filter rows)

- **Status:** Done
- **Owner:** Vũ
- **Created:** 2026-07-08
- **Related:** every filter feature that added a control to row 2 (search, exclude,
  match-nav, case, search-mode, presets)

## Goal

The single filter row has grown crowded (package controls, level, search, match nav,
exclude, regex, case, mode, clear). Split it into two clearer rows with light group
separators — no behavior change, just a more legible layout.

## Scope

- **In:** rearrange `_build_layout` into three rows:
  - **Row 1 (unchanged):** device + stream controls (+ Top/Latest, Follow).
  - **Row 2 — scope:** Package controls, then a separator, then Min level.
  - **Row 3 — search:** Search (stretch) + match nav + Regex/Case/Mode, a separator,
    Exclude, a separator, Clear filters.
  - Thin vertical separators (`QFrame.VLine`) group related controls; add "Search:" /
    "Exclude:" labels.
- **Out:** any widget/behavior/signal change; new features; theming changes.

## Design

Pure `ui/` layout. Same widgets, same wiring — only their arrangement changes.

| File | Layer | Change |
|---|---|---|
| `src/zlog/ui/main_window.py` | ui | `_build_layout` builds `row2` (scope) and `row3` (search) instead of one big `row2`; add a `_vsep()` helper returning a `QFrame.VLine`. Import `QFrame`. |

## Architecture touch points

- No model/proxy/threading change; no settings change; no new signals.
- Every widget keeps its identity, so all existing tests (which reference widgets by
  attribute) pass unchanged.
- Versioning: no bump.

## Risks & regressions to check

- All controls still present and wired (tests cover behavior; a screenshot confirms
  the visual arrangement).
- Window still fits at the default width; stretch on Search keeps it responsive.

## Verification

- [ ] `uv run pytest` (unchanged — behavior identical)
- [ ] `uv run ruff check .` and `uv run ruff format --check .`
- [ ] Headless screenshot shows two tidy filter rows with separators
