# Plan: Collapse repeated lines

- **Status:** Done
- **Owner:** unassigned
- **Created:** 2026-07-11
- **Related:** ROADMAP v1.4 "Reading & analysis", [exclude-filter.md](exclude-filter.md)

## Goal

After this ships, a **View → Collapse Repeated Lines** toggle hides consecutive
identical log lines (same level/tag/message), so a spammy loop that prints the
same line hundreds of times shows once instead of drowning the view. The status
bar's "showing X of Y" already communicates how many were folded.

## Scope

- **In:** a proxy filter gate that rejects a row when it's a consecutive duplicate
  (by level+tag+message) of the previous source row; a persisted View toggle.
- **Out:** a "×N" run-length badge on the kept line (needs delegate/model support;
  a follow-up), collapsing non-adjacent duplicates, folding stack traces.

## Design

| File | Layer | Change |
|---|---|---|
| `src/zlog/ui/log_model.py` | ui | `LogFilterProxy`: add `self._collapse = False` + `set_collapse(on)` (invalidates). In `filterAcceptsRow`, when collapse is on and `source_row > 0`, reject if `(level, tag, message)` equals the previous source row's. |
| `src/zlog/core/settings.py` | core | Add `"collapse": False`. |
| `src/zlog/ui/main_window.py` | ui | A checkable `collapse_action` in the View menu → `proxy.set_collapse`; settings spec `("collapse", isChecked, setter-that-also-applies)`. |
| `tests/test_log_model.py` | tests | With rows A,A,B,A, collapse shows 3 (the 2nd A folded); off shows 4; a duplicate hidden by another filter doesn't resurrect via collapse. |

## Architecture touch points

- **Proxy-only, virtualized:** the gate is O(1) per row (compare to the previous
  source entry); no model mutation, so toggling is instant and lossless.
- **Definition:** "consecutive" is source-adjacency — matches device spam ("same
  line N times in a row"); identity ignores time/pid so repeats still fold.

## Risks & regressions to check

- **Interaction with other gates:** a folded row is hidden regardless; the kept
  first-of-run still must pass level/search/etc. (it will, being identical).
- **First row:** `source_row == 0` always passes the collapse gate.
- **Status bar:** "showing X of Y" reflects the fold, so the reduction is visible.

## Verification

- [ ] `uv run pytest`
- [ ] `uv run ruff check .` and `uv run ruff format --check .`
- [ ] Manual: a repeated log line collapses to one; toggle off restores all.
