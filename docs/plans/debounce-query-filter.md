# Plan: Fix typing lag in the query bar

- **Status:** Done
- **Owner:** unassigned
- **Created:** 2026-07-15
- **Related:** [perf-start-freeze.md](perf-start-freeze.md) (same debounce/coalesce
  pattern, applied there to batch-arrival signals instead of typing)

## Goal

Typing in the query bar (`level:E tag:… -noise text`) no longer stutters/drops
keystrokes on a large capture — filtering is applied shortly after the user
pauses typing, not synchronously on every keystroke.

## Why (root cause)

`query.textChanged` is wired straight to `_apply_query`, so **every keystroke**
re-parses the query and pushes it through up to ~9 separate `LogFilterProxy`
setters (`set_levels`/`set_min_level`, `set_tag`, `set_query_pids`, `set_proc`,
`set_exclude_pids`, `set_exclude_proc`, `set_exclude`, plus the nested
`self.search.setText(...)` → `_apply_search` → `set_search` / `model.set_highlight`).
Each setter calls `self.invalidate()` **independently**, and `QSortFilterProxyModel
.invalidate()` re-runs `filterAcceptsRow` (a Python callback) over **every row** in
the master model (up to the 100,000-line ring-buffer cap). One keystroke can
therefore trigger on the order of 9 full O(n) passes, all synchronously on the
main thread before the next keypress is processed — the exact shape of the
"Not Responding" freeze `perf-start-freeze.md` already fixed for batch arrivals,
here triggered by typing instead.

## Scope

- **In:**
  1. **Debounce the query bar**: `query.textChanged` schedules a ~150ms
     single-shot timer instead of calling `_apply_query` directly; the timer's
     timeout is what actually applies. Typing continues to feel instant (the
     text field itself is never blocked); the expensive proxy work happens once
     after the user pauses. Pressing **Enter** (`_commit_query_history`) flushes
     immediately so committing a search doesn't feel delayed.
  2. **Collapse the ~9 invalidations into 1**: `LogFilterProxy` gets a
     `batch_update()` context manager; every existing setter's `self.invalidate()`
     is routed through a guarded `self._invalidate()` so, inside the context
     manager, all of them are deferred to a single `invalidate()` when the
     `with` block exits. `_apply_query` (and, transitively, `_apply_search`)
     wraps its body in `with self.proxy.batch_update():`.
- **Out:** debouncing the (hidden, programmatically-driven) `search`/`exclude`
  boxes' own direct signals — they're only ever driven through `_apply_query`
  now, so wrapping that entry point covers them; changing `filterAcceptsRow`'s
  per-row cost itself (a further optimization, not needed to fix the reported
  lag); debouncing the other `query.setText(...)` call sites (context-menu
  "Filter to…", mute-tag, preset activation, tab restore) — those are discrete
  clicks, not typing bursts, so inheriting the same ~150ms debounce is an
  acceptable, barely-perceptible trade-off rather than something to special-case.

## Design

| File | Layer | Change |
|---|---|---|
| `src/zlog/ui/log_model.py` | ui | `LogFilterProxy`: add `self._batching = False` in `__init__`; add `_invalidate(self)` (calls `self.invalidate()` only when not batching) and `batch_update(self)` (a `@contextmanager`: sets `_batching = True`, yields, then sets it back `False` and calls `self.invalidate()` once). Replace every setter's direct `self.invalidate()` with `self._invalidate()` (`set_min_level`, `set_search`, `set_exclude`, `set_levels`, `set_tag`, `set_pids`, `set_collapse`, `set_query_pids`, `set_proc`, `set_exclude_pids`, `set_exclude_proc`). |
| `src/zlog/ui/main_window.py` | ui | Add `self._query_timer` (single-shot, ~150ms) next to the existing `_scroll_timer`/`_counts_timer`. Change the `query.textChanged` connection from `self._apply_query` to a new trivial `self._schedule_query_apply` (`self._query_timer.start()`); the timer's `timeout` connects to `self._apply_query`. Wrap `_apply_query`'s body in `with self.proxy.batch_update():`. `_commit_query_history` (Enter) stops the pending timer and calls `_apply_query()` immediately before pushing history, so Enter never feels delayed. |
| `tests/test_log_model.py` | tests | `batch_update()` suppresses `invalidate()` until the block exits — assert via a monkeypatched/counted `invalidate` that N setter calls inside the block trigger exactly one real invalidate. |
| `tests/test_main_window_settings.py` | tests | Typing (simulated `textChanged` emissions / rapid `query.setText` calls without waiting) does not apply the filter until the timer fires; `QTest.qWait` past the interval applies it once; pressing Enter applies immediately without waiting. |

## Architecture touch points

- UI-only; no threading, no model virtualization change. `batch_update()` is a
  plain context manager around existing proxy state — no new Qt objects.
- Mirrors the `perf-start-freeze.md` debounce/coalesce pattern already used for
  `_update_counts`/`_scroll_timer`, so the codebase gets one more instance of an
  established idiom rather than a new one.

## Risks & regressions to check

- Every existing proxy-setter test must still see exactly one `invalidate()`
  when called standalone (outside a `batch_update()` block) — the guard must be
  a no-op when not batching.
- A `batch_update()` block that raises partway through must still invalidate
  exactly once on exit (use `try/finally`), so a bug elsewhere can't leave the
  proxy never refreshed.
- Rapid typing bursts (many `textChanged` emissions within the debounce
  window) must coalesce to exactly one applied filter, matching the final text
  — not one per keystroke and not a stale intermediate value.
- Enter must apply immediately, even mid-debounce.
- Preset save/load, saved-filter preview, and anything else that reads
  `self.proxy`'s *current* filtered state synchronously right after
  `query.setText(...)` (if any) must not read a stale pre-apply state because
  of the pending debounce — audit call sites that read proxy state right after
  setting the query text.

## Verification

- [x] `uv run pytest` (batch_update collapses N invalidates to 1; debounce
      coalesces a typing burst to one apply; Enter flushes immediately)
- [x] `uv run ruff check .` and `uv run ruff format --check .`
- [x] Bench (100k rows): a single unbatched `_apply_query()` — i.e. what used to
      run on **every keystroke** — took **1362 ms** across 10 separate
      `invalidate()` passes. Batched, the same call takes **124 ms** in one
      pass (~11x). Debouncing means that 124 ms now happens once per typing
      pause instead of once per keystroke; 21 simulated keystrokes with no
      wait took 0.2 ms total (nothing but timer restarts).

## Implementation note (revised during implementation)

The original plan assumed every other `query.setText(...)` call site (context
menu tokens, mute-tag, preset load, tab restore, level-dropdown sync, settings
restore) could tolerate inheriting the same ~150 ms debounce. That was wrong —
`_set_query_level` (dropdown sync) and `_load_and_apply_settings` (settings
restore) both read back the *result* of applying the query synchronously
(`level_box.currentData()`, proxy state), so debouncing them broke correctness,
not just snappiness (`test_settings_round_trip` caught it immediately).

Fix: `query.textChanged` is wired to a new trivial `_schedule_query_apply`
(starts the debounce timer) used **only** by genuine typing. Every other call
site now goes through a new `_set_query_text(text)` helper that blocks the
line edit's signals, sets the text, then calls `_apply_query()` directly —
applying immediately, exactly matching pre-debounce behavior. `_apply_query`
also stops the pending timer at its own top, so a direct call (Enter, a
toggle, `_set_query_text`) can't be followed by a redundant re-apply 150 ms
later.

Test fallout: many existing tests called `window.query.setText(...)` directly
to simulate a keystroke, then asserted on `proxy.rowCount()` synchronously —
exactly the case that must now be debounced. Added a shared `set_query(window,
text)` test helper (`tests/test_main_window_settings.py`) that sets the text
and flushes `_apply_query()` immediately, and switched every such call site to
it; a new `test_typing_in_query_bar_is_debounced` explicitly covers the
undebounced-until-flushed behavior instead.

## Open questions

- None blocking.
