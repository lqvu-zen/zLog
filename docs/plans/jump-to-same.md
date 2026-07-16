# Plan: Jump to same tag / PID

- **Status:** Done
- **Owner:** unassigned
- **Created:** 2026-07-16
- **Related:** ROADMAP "Reading & navigation" (P2), [match-navigation.md](match-navigation.md),
  [severity-navigation.md](severity-navigation.md), [quick-filter-pid-package.md](quick-filter-pid-package.md)

## Goal

After this ships, from a selected line you can jump to the next/previous visible
line with the **same tag** (or the **same PID**) — without filtering the view —
so following one component's or one process's thread through a noisy log is a
keypress instead of a scroll-and-scan.

## Scope

- **In:** four navigation actions — next/prev same-tag, next/prev same-PID —
  driven off the currently-selected row; operate over **visible** (proxy) rows;
  wrap around; right-click menu entries ("Next tag ‹Foo›", "Next PID ‹1234›")
  and shortcuts (`Alt+Down`/`Alt+Up` for tag, `Ctrl+Alt+Down`/`Ctrl+Alt+Up`
  for PID).
- **Out (non-goals):** jumping by process *name* (that's a proc: filter),
  jumping across hidden rows, a persistent "sticky selection" mode.

## Design

| File | Layer | Change |
|---|---|---|
| `src/zlog/ui/main_window.py` | ui | New `_goto_same(field, step)` — reads the current row's `entry` (via `_current_entry`), and if it has a non-empty value for `field` ("tag" or "pid"), scans visible proxy rows forward/backward from the cursor (then wraps) for the first whose `getattr(entry, field)` equals it, then selects+scrolls via the existing `_select_proxy_row`. This is the same early-exit-scan-then-wrap shape as `_goto_severity`, generalized over an equality predicate instead of a rank threshold. Four `QShortcut`s wired near the F3/match shortcuts (line ~861), plus context-menu entries in `_show_table_menu` (after the "Filter to…"/"Exclude…"/Isolate block, line ~2039) labeled with the actual tag/PID and disabled when the clicked row lacks that field. |
| `tests/test_main_window_settings.py` (or a small new `test_jump_to_same.py`) | tests | With rows I(TagA)/I(TagB)/I(TagA), selecting row 0 and `_goto_same("tag", 1)` lands on row 2; a further forward jump wraps to row 0; PID variant mirrored; a row whose field is empty is a no-op. |

## Architecture touch points

- **Proxy-based navigation:** the scan walks visible proxy rows, so it honors
  the active level/tag/search/package filters automatically — identical to
  `_goto_severity`/`_goto_bookmark`.
- **Early-exit scan:** walks from the cursor and stops at the first match, so
  it stays fast on large logs rather than materializing all matching rows.
- **No model/proxy/core changes** — this is pure MainWindow navigation reusing
  `_current_entry` + `_select_proxy_row`; `LogEntry` already carries `.tag`/`.pid`.

## Risks & regressions to check

- **No selection / empty field:** no selection, or a banner/unparsed row with
  an empty tag or pid → no-op, no crash, no selection change.
- **Only one matching row (itself):** forward/backward wrap returns to the same
  row (harmless), rather than getting stuck or erroring.
- **Shortcut collisions:** confirm `Alt+Down`/`Alt+Up`/`Ctrl+Alt+…` aren't
  already bound (grep `setShortcut`/`QShortcut`); pick free chords if they are.

## Verification

- [x] `uv run pytest` (365 passed; 1 pre-existing unrelated timing flake)
- [x] `uv run ruff check .` and `uv run ruff format --check .`
- [x] Screenshot skipped by design — behavior is a selection move; covered by
      `tests/test_jump_to_same.py` (skip-other-tags, wrap, PID variant,
      no-selection/empty-field no-ops)
- [x] Verified via unit tests + code review of the shortcut/menu wiring

## Open questions

None.
