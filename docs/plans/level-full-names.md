# Plan: Full level names in the query bar (case-insensitive)

- **Status:** Done
- **Owner:** unassigned
- **Created:** 2026-07-15
- **Related:** [level-multiselect.md](level-multiselect.md), [min-level-selector.md](min-level-selector.md)

## Goal

`level:error`, `level:Error`, `level:ERROR` (and `level:warn`/`warning`, `debug`,
`info`, `verbose`, `fatal`) all work the same as the existing single-letter
`level:E`, matching the full names already shown in the Level dropdown
(Verbose/Debug/Info/Warn/Error/Fatal).

## Why (bug, not just a missing feature)

`core/query.py`'s `level:` parsing today iterates the value **character by
character** (`[c for c in (ch.upper() for ch in val if ch != ",") if c in
_LEVELS]`), matching only single letters. Typing a full name doesn't just fail
to work — it silently produces the *wrong* result via coincidental letter
overlap: `level:error` happens to match only the `E` in "error" → behaves like
`level:E` (an accident, not by design), but `level:warning` matches both the
`W` in "warning" and the `I` in "warning" → is silently treated as the **exact
set** `{W, I}` instead of the intended "Warning and above" floor. This is a
real correctness bug, not only a missing convenience.

## Scope

- **In:** `level:` token values accept the six full names (`verbose`, `debug`,
  `info`, `warn`, `warning`, `error`, `fatal`) or single letters, case-insensitive,
  comma-separated for an exact set (`level:error,warning`), exactly mirroring
  today's single-letter comma-set behavior.
- **Out:** changing the Level dropdown or query-bar completer to suggest full
  names (out of scope — the dropdown already shows full names as display text;
  this is purely about what the query bar *parses*); adding abbreviations beyond
  the two existing colloquial spellings of Warn/Warning.

## Design

| File | Layer | Change |
|---|---|---|
| `src/zlog/core/query.py` | core | Replace the per-character scan with a `_LEVEL_ALIASES` dict (`{"v": "V", "verbose": "V", "d": "D", "debug": "D", "i": "I", "info": "I", "w": "W", "warn": "W", "warning": "W", "e": "E", "error": "E", "f": "F", "fatal": "F"}`) and a small `_parse_level_token(val) -> list[str]` that splits on `,`, lowercases each part, and looks it up — replacing the character-iteration bug with correct per-token matching. `parse_query`'s level branch and the module docstring's syntax summary are updated to mention full names. |
| `tests/test_query.py` | tests | Cases for each full name (both cases), the two Warn/Warning spellings, a full-name comma-set, and a mix of letter + full name (`level:E,warning`). |

## Architecture touch points

- Pure `core/` change, no Qt, no proxy/model touch — `parse_query` already
  feeds `QuerySpec.level`/`levels` into the existing proxy gates unchanged.

## Risks & regressions to check

- Existing single-letter behavior (`level:E`, `level:W,E`, `level:ZZZ` falling
  through to plain search text) must keep passing unchanged.
- A comma-set with only one recognized name (`level:bogus,error`) should still
  work correctly (dedup, ignore the unrecognized part) — same tolerance as
  today's `pid:` comma parsing.

## Verification

- [x] `uv run pytest` (new full-name/case-insensitive cases + existing tests green)
- [x] `uv run ruff check .` and `uv run ruff format --check .`
- [x] End-to-end through the real UI (MainWindow + proxy), 6-level seed data:
      `level:error`/`level:ERROR` → 2 rows (E+F, floor); `level:Warning`/`level:warn`
      → 3 rows (W+E+F, floor); `level:fatal,info` → 2 rows (exact set {F, I}) —
      confirms the old bug is gone (`level:warning` no longer becomes the
      accidental set `{W, I}`).
