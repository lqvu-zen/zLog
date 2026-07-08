# Plan: Phase 1 tech-debt cleanup (ruff pin + color/comment)

- **Status:** Done
- **Owner:** Vũ
- **Created:** 2026-07-07
- **Related:** [[tech-debt-refactor.md]] (Phase 1 of the tech-debt review: ruff pin + regex-error tint)

## Goal

Two zero-risk hygiene fixes: pin `ruff` so a surprise upgrade can't rewrite valid
code, and stop `main_window` from hardcoding a theme color / carrying a stale comment.

## Scope

- **In:** cap `ruff` in `pyproject.toml`; seed `self._search_error_color` from
  `THEMES["Light"].search_error` and delete the "once ui/theme.py exists" comment.
- **Out:** items 2–5 from the register (tests, CI, Python floor) — separate phases.

## Design

| File | Layer | Change |
|---|---|---|
| `pyproject.toml` | tooling | `"ruff>=0.5"` → `"ruff>=0.5,<0.16"` with a note re: the formatter gotcha. |
| `src/zlog/ui/main_window.py` | ui | `self._search_error_color = THEMES["Light"].search_error` (no literal hex); drop the stale parenthetical in `_apply_search`. |

## Architecture touch points

- No behavior change: `apply_theme` already overwrites `_search_error_color` from the
  active theme; this only fixes the *initial* value's source. Centralize-colors rule
  now satisfied (no hex at the widget). Versioning: no bump.

## Risks & regressions to check

- Regex-error tint still shows correctly under both themes (unchanged at runtime).
- `THEMES["Light"]` exists and exposes `search_error` (it does).

## Verification

- [ ] `uv run pytest`
- [ ] `uv run ruff check .` and `uv run ruff format --check .`
- [ ] Headless: invalid regex still tints the search box; toggling theme keeps it sane
- [ ] No literal `#ffd7d7` or "once that exists" left in `main_window.py`
