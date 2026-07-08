# Plan: Level multi-select

- **Status:** Draft
- **Owner:** Vũ
- **Created:** 2026-07-08
- **Related:** level-counts, package-filter

## Goal

Show only the specific levels you pick (e.g. just W+E+F), instead of only a minimum-
level floor — a common logcat need when hunting warnings/errors.

## Scope

- **In:** a level control that toggles individual levels (checkable menu or chips); the
  proxy accepts a set of allowed levels; persisted. Min-level remains as a quick preset.
- **Out:** per-tag level rules.

## Design

| File | Layer | Change |
|---|---|---|
| `src/zlog/ui/log_model.py` | ui | `LogFilterProxy` gains `set_levels(set|None)`; `filterAcceptsRow` checks membership when a set is active (else the existing min-level floor). |
| `src/zlog/ui/main_window.py` | ui | A checkable "Levels" menu (V..F); persisted as `levels`. |
| `src/zlog/core/settings.py` | core | Add `"levels": []` (empty = use min-level floor). |

## Architecture touch points

- One more proxy gate over the intact master list; unparsed lines still pass.
- Versioning: no bump.

## Risks & regressions to check

- Interaction between min-level and the explicit set (define precedence + test).
- Round-trips through settings; spec-parity holds.

## Verification

- [ ] `uv run pytest` (proxy level-set gate + round-trip)
- [ ] `uv run ruff check .` and `uv run ruff format --check .`
