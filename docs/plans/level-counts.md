# Plan: Level-count summary in the status bar

- **Status:** Done  <!-- Draft | Approved | In progress | Done | Abandoned -->
- **Owner:** Vũ
- **Created:** 2026-07-01

## Goal

Show a live tally of the captured log in the status bar — total line count plus a
per-level breakdown (how many Fatal/Error/Warning/…) — so severity is visible at a
glance without scrolling.

## Scope

- **In:** a permanent status-bar readout, e.g. `1,204 lines  F:2 E:12 W:30 I:900`,
  covering the **whole captured log** (the master list), updated as lines arrive and
  reset on Clear / Open Log. Zero-count levels are omitted.
- **Out (non-goals):** counts of the *filtered* view (shown counts are of everything
  captured); clickable counts that set a filter; charts.

## Design

Counting is maintained incrementally in the model (O(batch), not a rescan); the
status-line formatting is a pure function in `core` so it's unit-testable.

| File | Layer | Change |
|---|---|---|
| `src/zlog/core/summary.py` (new) | core | `format_level_summary(total: int, counts: dict[str, int]) -> str` — renders `"{total:,} lines  F:.. E:.. W:.. I:.. D:.. V:.."`, severity-first, omitting zero counts. Pure, no Qt. |
| `src/zlog/core/__init__.py` | core | export `format_level_summary`. |
| `src/zlog/ui/log_model.py` | ui | keep a `collections.Counter` of levels; `append_entries` increments it, `clear` resets it; add `level_counts() -> dict[str, int]`. |
| `src/zlog/ui/main_window.py` | ui | add a permanent `QLabel` to the status bar via `addPermanentWidget`; `_update_counts()` sets its text from `format_level_summary(self.model.rowCount(), self.model.level_counts())`. Wire `self.model.rowsInserted` and `self.model.modelReset` to `_update_counts` so it stays current on append/clear/load. Drop the transient `"{n} lines"` message from `on_batch` (the permanent label now shows it). |
| `tests/test_summary.py` (new) | tests | empty → `"0 lines"`; counts present → correct order/format; zero-count levels omitted; thousands separator. |
| `.claude/skills/run-zlog/scripts/driver.py` | (skill) | `populated` already exercises it; optionally assert the label text in a quick check. |

## Architecture touch points

- **Threading/model:** counts update on the main thread from the model's own
  insert/reset signals; no rescans, model stays virtualized.
- **Dependency direction:** formatting is pure `core/summary.py`; the model owns the
  `Counter`; the UI just renders. `core` stays Qt-free.
- **Status bar:** the count label is a *permanent* widget (right side), independent of
  the transient `showMessage` area used for actions/errors — they won't clobber each
  other.
- **Versioning:** no bump (release-only).

## Risks & regressions to check

- Counts match the actual rows after appends, Clear, and Open Log.
- Transient messages (Copied, Streaming…, filter notes) still show and don't erase
  the counts, and vice-versa.
- No perceptible slowdown under high-volume streaming (increment is O(batch)).
- Unparsed/banner lines (level `""`) are counted as total but not under any letter.

## Verification

- [x] `uv run pytest` (new `test_summary.py` green)
- [x] `uv run ruff check .` and `uv run ruff format --check .`
- [x] `run-zlog` `populated` screenshot shows the count summary in the status bar
- [ ] Manual: stream, watch counts climb; Clear resets to `0 lines`; Open a file → its counts

## Open questions

- Order **severity-first (F,E,W,I,D,V)** (proposed) or ascending (V→F)?
- Count the **whole capture** (proposed) or the current filtered view?
