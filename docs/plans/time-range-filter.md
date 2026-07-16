# Plan: Time-range filter (since:/until:)

- **Status:** Done
- **Owner:** unassigned
- **Created:** 2026-07-16
- **Related:** ROADMAP "Filtering & search" (P1), [goto-line-time.md](goto-line-time.md),
  [quick-filter-pid-package.md](quick-filter-pid-package.md)

## Goal

After this ships, typing `since:12:34:00` and/or `until:12:36:00` in the query bar
bounds the view to lines whose timestamp falls in that time-of-day range — so
narrowing a long capture to "just the minute the bug happened" is a query token,
not manual scrolling.

## Scope

- **In:** two new query tokens, `since:HH:MM:SS[.mmm]` and `until:HH:MM:SS[.mmm]`
  (either or both may be given), inclusive bounds, parsed the same lenient way as
  `Go to time…`; a proxy gate; token-bar syntax highlighting for both keys.
- **Out (non-goals):** an absolute-date range (captures are single-day, same
  assumption `core/timefmt.py` already documents), a visual range picker/slider,
  relative durations (`since:-30s`).

## Design

| File | Layer | Change |
|---|---|---|
| `src/zlog/core/query.py` | core | Add `since: str = ""` and `until: str = ""` fields to `QuerySpec` (line 56). In `parse_query`'s `key:value` branch (~line 114-139), add `elif key == "since" and val: since = val` / `elif key == "until" and val: until = val` alongside the existing `pid`/`proc` cases — raw string, not pre-parsed, so an invalid value can be flagged the same way regex errors are. Add `"since"`/`"until"` to `_classify` (line 158-176) and document the syntax in the module docstring. |
| `src/zlog/core/timefmt.py` | core | New `in_time_range(stamp: str, since: time \| None, until: time \| None) -> bool` — parses `stamp` via `parse_logcat_time(stamp).time()`; an unparseable stamp passes (consistent with how the level gate already lets unparsed lines through); `since`/`until` are each optional, checked with `>=`/`<=` (inclusive). |
| `src/zlog/ui/log_model.py` | ui | `LogFilterProxy.__init__`: `self._since: time \| None = None`, `self._until: time \| None = None`. New `set_time_range(since: time \| None, until: time \| None) -> None` setter (mirrors `set_tag`) calling `self._invalidate()`. `filterAcceptsRow` (line 496): one new early-return using `in_time_range(entry.time, self._since, self._until)`, placed with the other gates (after the level gate, before tag — cheap, so early-out only saves work on rows already past pid/level checks; exact position isn't perf-critical since the check itself is O(1)). |
| `src/zlog/ui/main_window.py` | ui | `_apply_query` (line 1208): parse `spec.since`/`spec.until` via `parse_time_of_day`; track validity like the existing `ex_ok`/`search_ok` flags (an unparseable `since:`/`until:` value should tint the query bar red via the existing error stylesheet, not silently no-op) and call `self.proxy.set_time_range(...)` inside the existing `batch_update()` block. |
| `tests/test_query.py` | tests | `parse_query("since:12:00:00 until:12:05:00")` round-trips both fields; `token_spans` classifies both keys. |
| `tests/test_timefmt.py` | tests | `in_time_range` — inside/outside/only-since/only-until/unparseable-stamp cases. |
| `tests/test_log_model.py` | tests | `LogFilterProxy.set_time_range` hides rows outside the bound, in the `_wire`/`_entry`/`_messages` style already used for other gates. |

## Architecture touch points

- **Qt-free core:** `in_time_range` lives in `core/timefmt.py` next to `parse_logcat_time`/`first_at_or_after`, zero Qt, directly unit-tested.
- **Single wiring point:** all filtering still flows through `_apply_query` → `proxy.batch_update()`, so this doesn't add a second filter path.
- **Proxy, not master list:** the gate is a new `filterAcceptsRow` branch; `_rows` stays untouched, so clearing `since:`/`until:` is instant.
- **Reuses `parse_time_of_day`** (already used by `Go to time…`) rather than inventing new parsing — one time-string format for the whole app.

## Risks & regressions to check

- **Unparseable value:** `since:notatime` must not silently show nothing or
  everything — flag it the same way an invalid regex is flagged (query bar red
  tint), and keep the previous range (mirrors `set_search`/`set_exclude`'s
  "return False, keep old state" contract).
- **Only one bound given:** `since:` alone filters open-ended forward; `until:`
  alone filters open-ended backward — both must work independently.
- **Unparsed/banner lines** (`entry.time == ""`) must still pass (same rule as
  the level gate), not get hidden by a strict time comparison.
- **Interaction with relative-time display mode:** the gate always compares the
  raw absolute timestamp, regardless of the Time column's display mode
  (absolute/since-start/delta) — the two are independent, confirm no coupling
  creeps in.

## Verification

- [x] `uv run pytest` (335 passed; 1 pre-existing unrelated timing flake, see
      crash-anr-detector.md)
- [x] `uv run ruff check .` and `uv run ruff format --check .`
- [x] Smoke / screenshot via `run-zlog` (new `time-range-filter` scenario):
      `since:12:34:56.110` correctly hides the two earliest rows and keeps the
      unparseable banner line ("Showing 20 of 28 lines")
- [x] Manual: verified via the driver scenario; `since` alone, `until` alone,
      and the invalid-value error-tint path are covered by
      `tests/test_timefmt.py`/`tests/test_log_model.py`/`tests/test_query.py`

## Open questions

None.
