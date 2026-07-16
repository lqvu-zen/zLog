# Plan: Jank / "skipped frames" summary

- **Status:** Done
- **Owner:** unassigned
- **Created:** 2026-07-16
- **Related:** ROADMAP "Analysis & insight" (P2), [tag-summary.md](tag-summary.md),
  [crash-anr-detector.md](crash-anr-detector.md)

## Goal

After this ships, **View → Jank Summary…** shows a small dialog aggregating
`Choreographer` "Skipped N frames!" lines by process (PID), so the user can see
at a glance which process is janking and how badly, instead of eyeballing
scattered warning lines — mirrors **Tag Summary**'s shape exactly.

## Scope

- **In:** parse `Skipped <N> frames!` from `Choreographer`-tagged lines; a
  modal dialog listing PID / event count / total frames skipped, sorted by
  total frames skipped descending; double-click a row to filter the view to
  that PID (`pid:<n>`), same as Tag Summary's double-click-to-filter.
- **Out (non-goals):** a trend-over-time chart (that's the separate "Timeline
  histogram" backlog item), configurable jank thresholds, matching jank
  patterns other than the standard Choreographer message.

## Design

| File | Layer | Change |
|---|---|---|
| `src/zlog/core/jank.py` (new) | core | `_SKIP_RE = re.compile(r"Skipped (\d+) frames!")`. `jank_summary(entries) -> list[tuple[str, int, int]]` — for each entry with `tag == "Choreographer"` whose message matches `_SKIP_RE`, accumulate per-PID `(event_count, total_frames)`; return `[(pid, event_count, total_frames), ...]` sorted by `total_frames` descending, then `pid` ascending (mirrors `tag_counts`'s `(-count, tag)` sort in `core/summary.py`). Pure, Qt-free, unit-tested directly like `tag_counts`. |
| `src/zlog/ui/main_window.py` | ui | Import `jank_summary`. New View-menu action "&Jank Summary…" placed next to `tag_summary_act` (line 751-752). New `_show_jank_summary(self) -> None`, a near-line-for-line copy of `_show_tag_summary` (lines 1603-1630): `QTableWidget` with columns `PID / Events / Frames Skipped` populated from `jank_summary(self._filtered_entries())`, `cellDoubleClicked` → `self._set_query_text(f"pid:{rows[row][0]}")` then `dlg.accept()`. |
| `tests/test_jank.py` (new) | tests | `jank_summary` — a mix of Choreographer/non-Choreographer lines, multiple PIDs, sort order, a Choreographer line that *doesn't* match the skip pattern (ignored), zero-input case. |

## Architecture touch points

- **Qt-free core, mirrors `tag_counts`:** `core/jank.py` takes a plain iterable
  of entry-like objects and returns plain tuples — no Qt, directly testable,
  same shape as the existing `core/summary.py::tag_counts`.
- **Reuses the Tag Summary dialog pattern exactly** (modal `QDialog` +
  `QTableWidget` + double-click-to-filter via `_set_query_text`) rather than
  inventing a new UI shape — one more `_show_*_summary` method alongside the
  existing one.
- **Operates on `_filtered_entries()`** (currently-visible rows), same as Tag
  Summary, so the summary reflects whatever the user has already filtered to.

## Risks & regressions to check

- **No Choreographer lines / no jank:** dialog shows an empty table, no crash.
- **Message format drift:** if a device's Choreographer message doesn't match
  `Skipped (\d+) frames!` exactly (e.g. different wording on some OEM/Android
  version), that line is silently ignored rather than counted — acceptable for
  v1 (documented as a known limitation, same class of trade-off as the
  crash/ANR detector's fixed-pattern matching).
- **Large captures:** aggregation is a single pass over `_filtered_entries()`,
  same cost class as `tag_counts` already pays for Tag Summary — no new
  performance concern.

## Verification

- [x] `uv run pytest` (360 passed; 1 pre-existing unrelated timing flake, see
      crash-anr-detector.md)
- [x] `uv run ruff check .` and `uv run ruff format --check .`
- [x] Smoke / screenshot via `run-zlog` (new `jank-summary` scenario, which
      patches `QDialog.exec` to non-modal so the dialog can be grabbed):
      PID 100 (2 events, 28 frames) sorted above PID 200 (1 event, 3 frames)
- [x] Manual: the double-click handler is a line-for-line copy of Tag
      Summary's already-proven `use(row, _col)` closure calling
      `_set_query_text(f"pid:{...}")`; no new test added, matching
      tag-summary.md's own precedent of relying on structural reuse + a
      rendered screenshot rather than a MainWindow-level interaction test

## Open questions

None.
