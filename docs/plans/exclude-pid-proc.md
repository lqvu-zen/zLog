# Plan: Exclude by pid / proc

- **Status:** Done
- **Owner:** unassigned
- **Created:** 2026-07-15
- **Related:** [quick-filter-pid-package.md](quick-filter-pid-package.md), [exclude-filter.md](exclude-filter.md), backlog.md

## Goal

`-pid:1234` and `-proc:com.x` in the query bar hide lines from that PID / that
resolved process, complementing the existing `pid:`/`proc:` includes; also
reachable from the log's right-click menu ("Exclude this PID" / "Exclude this
package").

## Scope

- **In:** query-bar negative tokens for pid and proc; a proxy-level exclude gate
  for each; two new context-menu actions on the table.
- **Out (non-goals):** negative `tag:`/`package:` tokens (the generic `-word`
  exclude already covers ad-hoc text; structured negatives stop at pid/proc per
  the backlog item); excluding a set of packages at once beyond comma-separated PIDs.

## Design

| File | Layer | Change |
|---|---|---|
| `src/zlog/core/query.py` | core | In `parse_query`, before a bare `-word` falls into the generic `excludes` list, check for `-pid:` / `-proc:`(`-process:`) and parse them like their positive counterparts. New `QuerySpec` fields: `exclude_pids: tuple[str, ...] = ()` (comma-set, mirrors `pids`), `exclude_process: str = ""` (mirrors `process`, last-token-wins). `_classify`/`token_spans` already return `"exclude"` for any `-`-prefixed token, so query-bar coloring needs no change. |
| `src/zlog/ui/log_model.py` | ui | `LogFilterProxy`: `_exclude_pids: set[str] \| None`, `_exclude_proc: str` + `set_exclude_pids(pids)` / `set_exclude_proc(text)` setters (each calls `invalidate()`). In `filterAcceptsRow`, add the negative checks next to the existing `_query_pids`/`_proc` include gates: reject if `entry.pid in self._exclude_pids`, or if `self._exclude_proc` is truthy and contained in `model.process_name(entry.pid).lower()`. |
| `src/zlog/ui/main_window.py` | ui | In `_apply_query`, wire `proxy.set_exclude_pids(set(spec.exclude_pids) or None)` and `proxy.set_exclude_process(spec.exclude_process)` next to the existing `set_query_pids`/`set_proc` calls. Context menu (`_show_table_menu`): "Exclude this PID" / "Exclude this package" call `_add_query_token("-pid:<pid>")` / `_add_query_token("-proc:<name>")` (reusing the existing add-token helper — same mechanism `quick-filter-pid-package` uses for the positive actions). |

## Architecture touch points

- **Model/proxy:** two new filter predicates via `filterAcceptsRow` + setters
  calling `invalidateFilter`/`invalidate()`, mirroring the existing include gates
  exactly — no new column, no threading.
- **Dependency direction** unchanged (`ui → adb → core`); `core/query.py` stays Qt-free.

## Risks & regressions to check

- A pid/proc appearing in both the include and exclude token (e.g. `pid:100
  -pid:100`) must exclude — apply exclude checks after include checks, same
  precedence as the existing generic `-noise` exclude vs. search.
- Empty `-proc:` value from a stray token doesn't turn into an "exclude
  everything" gate (falsy empty string is treated as off, mirroring `_proc`).
- Comma-set parsing for `-pid:100,200` matches the existing `pid:` comma parsing.

## Verification

- [x] `uv run pytest` (`parse_query` new cases: `-pid:`, `-proc:`, combined with
      positive tokens; proxy `filterAcceptsRow` exclude-gate tests)
- [x] `uv run ruff check .` and `uv run ruff format --check .`
- [x] Headless smoke: app renders with no regressions (`run-zlog` driver)

## Open questions

- None blocking.
