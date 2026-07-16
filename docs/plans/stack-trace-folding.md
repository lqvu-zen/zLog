# Plan: Stack-trace folding

- **Status:** Done
- **Owner:** unassigned
- **Created:** 2026-07-16
- **Related:** ROADMAP "Reading & navigation" (P2), [collapse-repeats.md](collapse-repeats.md),
  [crash-anr-detector.md](crash-anr-detector.md), [duplicate-count.md](duplicate-count.md)

## Goal

After this ships, the `at …` frames of a Java exception collapse under their
header line into a single "▶ … N frames" disclosure that you can expand — so a
40-line stack trace becomes one scannable line, and a log full of crashes stays
readable. A **View → Fold Stack Traces** toggle folds/unfolds them all at once;
clicking a header's triangle toggles just that trace.

## Scope

- **In:** detect consecutive stack-frame lines (`at …`, `… N more`); a fold
  state per trace (header row); the proxy hides folded frame lines; the delegate
  draws a ▶/▼ disclosure and a "… N frames" hint on a folded header; click the
  triangle to toggle one trace; a **Fold Stack Traces** View toggle
  (fold-all / unfold-all), persisted.
- **Out (non-goals):** folding non-Java traces (native backtraces, tombstones),
  folding arbitrary user-chosen ranges, remembering per-trace fold state across
  restarts (only the global toggle persists), nested/partial fold levels.

## Design

A **stack frame** is a line whose message matches `^\s*at ` or
`^\s*\.\.\. \d+ more` (Qt-free, in `core/trace.py`). A frame's **header** is the
nearest preceding row that is *not* a frame; consecutive frames after a header
form one trace.

| File | Layer | Change |
|---|---|---|
| `src/zlog/core/trace.py` (new) | core | `is_stack_frame(message: str) -> bool` (the two regexes above). `frame_hint(n: int) -> str` → e.g. `"… 27 frames"`. Pure, unit-tested. |
| `src/zlog/ui/log_model.py` | ui | Maintain `self._frame_header: list[int]` parallel to `_rows` (header source row for a frame, else `-1`) and `self._header_frames: dict[int, int]` (header row → frame count), both built in `append_entries` O(1): if `is_stack_frame(entry.message)` and the previous row is a frame, inherit its header; elif `is_stack_frame` and previous is not a frame, header = previous row index; else `-1`. Increment `_header_frames[header]`. Fold state: `self._folded: set[int]` (folded header rows). Methods: `is_frame_hidden(source_row) -> bool` (`_frame_header[row] in _folded`), `header_at(row)`, `frame_count(header)`, `toggle_fold(header)`, `fold_all()`/`unfold_all()` (fill/clear `_folded` over headers with frames), `is_folded(header)`. `toggle_fold`/`fold_all`/`unfold_all` emit `layoutChanged` (via the proxy invalidation path) and a `dataChanged` repaint of the header. `clear()` resets all three; `_enforce_cap()` shifts `_frame_header` and remaps `_folded`/`_header_frames` like `_bookmarks`/`_incidents` (or, per Open questions, clears `_folded` on trim to cut bookkeeping). A new `FOLD_ROLE = int(Qt.UserRole) + 5` in `data()` returns `(is_header_with_frames, is_folded, frame_count)` for the delegate. |
| `src/zlog/ui/log_model.py` (proxy) | ui | `LogFilterProxy.filterAcceptsRow`: add an early-return `if self.sourceModel().is_frame_hidden(source_row): return False`, gated so it's a no-op when nothing is folded. A `set_fold_enabled`/invalidate hook isn't needed — folding mutates model state then invalidates the proxy. |
| `src/zlog/ui/log_delegate.py` | ui | On a header row that has frames (`FOLD_ROLE`), draw a ▶ (folded) / ▼ (expanded) glyph at the message start and, when folded, append the `frame_hint(n)` after the header text. Expose the disclosure hit-rect geometry (x-range of the glyph) so the view can hit-test it — e.g. a `disclosure_rect(option_rect)` helper or a documented constant offset from `message_x`. |
| `src/zlog/ui/table_view.py` | ui | Override `mousePressEvent`: if the click's `indexAt(pos)` is a header-with-frames and lands in the disclosure rect, call back to toggle that header's fold (via a signal `fold_toggled(source_row)` or a set callback) and consume the event (no selection change). Non-disclosure clicks fall through to normal selection. |
| `src/zlog/ui/main_window.py` | ui | A checkable `self.fold_action` ("Fold Stack Traces", built with the other View toggles ~line 706) → `model.fold_all()`/`unfold_all()` + `proxy.invalidate()` + repaint. Connect the view's `fold_toggled` to `model.toggle_fold` + invalidate. Add `fold_action` to the View menu and to `_settings_specs()` (`("fold_traces", self.fold_action.isChecked, set_fold)` with a matching `DEFAULTS` key). |
| `src/zlog/core/settings.py` | core | Add `"fold_traces": False` to `DEFAULTS`. |
| `tests/test_trace.py` (new) | tests | `is_stack_frame` true for `"\tat com.x.Y.z(Y.java:1)"` and `"\t... 27 more"`, false for ordinary messages; `frame_hint`. |
| `tests/test_log_model.py` | tests | Header + 3 frames: `header_at(frame_row)` points at the header, `frame_count(header) == 3`; `toggle_fold(header)` then `proxy` hides exactly the 3 frame rows (header still visible); `unfold_all()` restores them; a non-trace log is unaffected. |

## Architecture touch points

- **Qt-free detection:** frame classification lives in `core/trace.py`, directly
  unit-tested — mirrors `core/incidents.py`'s pattern-matching split from the UI.
- **Incremental, O(1) per append:** header/frame bookkeeping rides the existing
  `append_entries` loop (like `_level_counts`/`_incidents`), so streaming stays
  responsive; no O(n) rescan on fold toggles (fold just flips a set + invalidates).
- **Proxy-gated hiding:** folded frames are hidden via `filterAcceptsRow`, so
  they interact correctly with every other filter and keep the master list
  intact — folding is reversible instantly. Consistent with collapse-repeats.
- **Model virtualized:** `FOLD_ROLE` is a `data()` lookup; the delegate paints
  only visible rows; no per-row widgets, no `beginResetModel` on a fold toggle
  (uses `invalidateFilter`/`layoutChanged`).

## Risks & regressions to check

- **Ring-buffer trim bookkeeping:** `_frame_header` is index-based and must shift
  with the front trim; `_folded`/`_header_frames` are header-row-keyed and must
  remap (or be cleared) on trim — the highest-risk part. Test a trim that drops
  a header while keeping its frames (frames should reappear, not stay orphaned-
  folded) and a trim that keeps the header. **Open question**: clearing `_folded`
  on trim is a simpler, acceptable alternative (fold is transient UI state).
- **A frame with no header** (a trace at source row 0, or after a banner):
  `_frame_header` is `-1` → never hidden, always shown. No crash.
- **Interaction with collapse-repeats / duplicate-count:** confirm the two
  proxy gates compose (a folded frame that is also a duplicate stays hidden;
  order of gates doesn't matter since both only hide).
- **Click hit-testing fragility:** the disclosure rect in the view must match
  the delegate's drawn glyph position. Keep the geometry in one place (a shared
  helper/constant) so they can't drift; verify by screenshot. Fallback if pixel
  math is fragile: also toggle on double-click of a header-with-frames row.
- **Selection/scroll:** toggling a fold must not steal Follow or jump the
  viewport unexpectedly (folding removes rows below; keep the header selected).

## Implementation notes

- **Per-trace interaction = double-click** the header row (not pixel-precise
  triangle hit-testing) — robust and testable; the ▶/▼ glyph is the visual
  affordance. `LogTableView.mouseDoubleClickEvent` emits `fold_toggle_requested`
  with the source row; MainWindow toggles the model + invalidates the proxy.
- **Global toggle:** View → **Fold Stack Traces** (`fold_all`/`unfold_all`),
  persisted via `_settings_specs` (`fold_traces`).
- **Known limitation (live streaming):** folding applies to traces already in
  the buffer; traces that arrive *after* the toggle is on are not auto-folded
  (re-toggle to fold them). The primary use case — reading an opened/captured
  crash log — loads fully before folding, so it's unaffected.

## Verification

- [x] `uv run pytest` (384 passed; 1 pre-existing unrelated timing flake)
- [x] `uv run ruff check .` and `uv run ruff format --check .`
- [x] Smoke / screenshot via `run-zlog` (new `stack-trace-folding` scenario):
      the `java.lang.RuntimeException` header shows ▶ + "… 4 frames", the 4
      frames hide, the non-frame `FATAL EXCEPTION` line stays; "Showing 4 of 8"
- [x] Manual: covered by `tests/test_trace.py` (detection) and
      `tests/test_log_model.py` (grouping, fold hides exactly the frames,
      fold_all/unfold_all, non-header toggle no-op, non-trace log unaffected)

## Open questions

- **Trim policy for fold state:** DECIDED (2026-07-16) — **clear `_folded` on
  trim**. `_frame_header` still shifts with the front trim (it's index-based),
  but fold state resets when old lines roll off the cap, avoiding header-key
  remapping. Fold is transient UI state, so this is acceptable.
- **Per-trace click vs. global-only:** if the delegate hit-testing proves
  fragile in review, ship the global **Fold Stack Traces** toggle first and add
  per-header triangle clicks as a follow-up.
