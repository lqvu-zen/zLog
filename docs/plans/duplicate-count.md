# Plan: Duplicate-count badge (×N) on collapsed lines

- **Status:** Done
- **Owner:** unassigned
- **Created:** 2026-07-16
- **Related:** ROADMAP "Filtering & search" (P2), [collapse-repeats.md](collapse-repeats.md)

## Goal

After this ships, when **Collapse Repeated Lines** is on, the surviving
representative of a run of identical lines shows a small **×N** badge (N = how
many identical lines it stands for) instead of silently swallowing the
duplicates — so the reduction is visible and you can tell "this fired 400 times"
from "this fired twice."

## Scope

- **In:** a per-run duplicate count maintained on the model; a `DUP_COUNT_ROLE`
  the delegate reads; the delegate paints a `×N` badge (only when collapse mode
  is on and N > 1) just before the message. Count is total run length (the
  representative + its hidden duplicates).
- **Out (non-goals):** counting duplicates when collapse is *off* (there's no
  representative to hang the badge on), a separate sortable column, non-adjacent
  duplicate detection (only consecutive, matching the existing collapse rule).

## Design

Identical lines are defined exactly as the collapse gate already defines them:
same `(level, tag, message)` as the immediately preceding row
(`log_model.py:549`).

| File | Layer | Change |
|---|---|---|
| `src/zlog/ui/log_model.py` | ui | Maintain `self._run_len: list[int]` parallel to `_rows`: in `append_entries`, for each new entry, if it equals the previous row's `(level, tag, message)` push `0` and increment the run's representative entry (`self._run_len[rep] += 1`, tracking `rep` = index of the current run's first row); else it starts a new run, push `1`, `rep = i`. O(1) per appended line, mirroring how `_level_counts`/`_incidents` are maintained in the same loop. `clear()` resets it; `_enforce_cap()` trims the front slice like `_bookmarks`/`_incidents` (see risk note on the boundary run). New `run_length(source_row) -> int` accessor and a `DUP_COUNT_ROLE = int(Qt.UserRole) + 4`; `data()` returns `self._run_len[row]` for it (only representatives carry >0; hidden duplicates carry 0 and are never painted anyway). |
| `src/zlog/ui/log_delegate.py` | ui | New `self.collapse = False` flag (set by MainWindow, like `self.wrap`). In `paint`, after the level chip and before drawing the message, if `self.collapse` and `index.data(DUP_COUNT_ROLE) > 1`, draw a compact `×N` badge (muted pill) and advance `x` by its width so the message starts after it. Reuse the existing metadata color; no new theme token needed (a subtle box like the level chip, but using `self._muted`). |
| `src/zlog/ui/main_window.py` | ui | Set `self.log_delegate.collapse` wherever `proxy.set_collapse` is called (the `collapse_action.toggled` slot at line 708 and `set_collapse` in `_settings_specs` at line 2423) and repaint the viewport, so the badge appears/disappears with the toggle. |
| `tests/test_log_model.py` | tests | Append A,A,A,B → `run_length(0) == 3`, `run_length(3) == 1`; `DUP_COUNT_ROLE` returns those; a cap that trims mid-run behaves per the documented boundary rule. |

## Architecture touch points

- **Incremental, O(1) per append:** run length is accumulated in the existing
  append loop alongside `_level_counts`, so a busy stream doesn't pay an O(n)
  rescan (keeps Start responsive — see perf-start-freeze.md).
- **Model virtualized:** `DUP_COUNT_ROLE` is a plain `data()` lookup; the
  delegate paints only visible rows. No column added (`COLUMNS` unchanged),
  matching how the grid-less delegate already renders everything in column 0.
- **Reuses the collapse definition of "duplicate"** — one source of truth for
  what counts as identical, so the badge and the hiding never disagree.

## Risks & regressions to check

- **Ring-buffer trim across a run boundary:** if the cap drops a run's
  representative but keeps some of its duplicates, the new front row was a
  hidden duplicate (run_len 0). The collapse gate always shows source row 0
  (no previous to compare), so it becomes visible but would show no ×N.
  **Accepted limitation** (one row, only on a capped + spammy log, purely
  cosmetic); documented here and in the test. Simpler than re-deriving run
  heads on every trim.
- **Collapse off:** `DUP_COUNT_ROLE` is ignored by the delegate (gated on
  `self.collapse`), so counts never show when every line is visible.
- **Selection/highlight interaction:** the badge draws before the message in
  the same row; confirm it doesn't overlap the inline-match-highlight spans
  (advance `x` past the badge before computing the message rect).
- **Wrap mode:** the badge sits on the first (band) line like the other
  metadata; confirm it doesn't get pushed into the wrapped body.

## Verification

- [x] `uv run pytest` (368 passed; 1 pre-existing unrelated timing flake)
- [x] `uv run ruff check .` and `uv run ruff format --check .`
- [x] Smoke / screenshot via `run-zlog` (new `duplicate-count` scenario): a run
      of 6 identical GnssHal lines collapses to one row showing a boxed `×6`
      badge; status bar "Showing 2 of 7 lines"
- [x] Manual: covered by `tests/test_log_model.py` (run_length across batches,
      DUP_COUNT_ROLE, cap-boundary promotion) + the screenshot

## Open questions

None — the boundary-run cosmetic limitation is accepted above; flag in review
if exact counts at the cap boundary are wanted (would need run-head re-derivation
on trim).
