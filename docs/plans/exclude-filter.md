# Plan: Exclude / negative filter

- **Status:** Done
- **Owner:** Vũ
- **Created:** 2026-07-08
- **Related:** regex-search, package-filter, highlight-matches

## Goal

Hide lines matching an "exclude" term (substring or regex) — the inverse of search —
so a noisy tag or pattern can be muted while everything else stays visible.

## Scope

- **In:** an **Exclude** field next to the search box; rows whose `tag + message`
  match the exclude term are hidden. Reuses the existing Regex/Case toggles. A new
  proxy predicate; Clear Filters also clears it.
- **Out:** multiple independent exclude terms; per-column excludes; persisting the
  exclude text (transient, like the search box).

## Design

The proxy already gates on level/search/PID; add one more gate.

| File | Layer | Change |
|---|---|---|
| `src/zlog/ui/log_model.py` | ui | `LogFilterProxy` gains `_exclude` (default None = exclude nothing); `set_exclude(text, regex, case) -> bool` compiles a matcher (empty → None); `filterAcceptsRow` returns False when the exclude matcher matches. |
| `src/zlog/ui/main_window.py` | ui | Add `self.exclude` line edit to row 2; `_apply_search` (renamed intent) also calls `proxy.set_exclude(...)` with the shared Regex/Case flags; `clear_filters` clears it. Invalid-regex handling mirrors search. |

## Architecture touch points

- Filtering stays in the proxy over the intact master list; clearing exclude is instant.
- Reuses `core.search.compile_matcher` — no new core code. Colors/UI rules unaffected.
- Versioning: no bump.

## Risks & regressions to check

- Exclude gate runs before/after level & search gates consistently; unparsed lines
  (empty tag/message) aren't accidentally excluded by an empty term.
- Invalid exclude regex keeps the previous exclude matcher, flags the box.
- Clear Filters resets exclude; empty exclude shows everything.

## Verification

- [ ] `uv run pytest` (proxy exclude-gate tests, incl. combined with search/level)
- [ ] `uv run ruff check .` and `uv run ruff format --check .`
- [ ] Headless: seed rows, set exclude, assert matching rows hidden and others kept
