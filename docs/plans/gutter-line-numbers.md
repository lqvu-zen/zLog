# Plan: Gutter line numbers

- **Status:** Approved  <!-- Draft | Approved | In progress | Done | Abandoned -->
- **Owner:** Claude
- **Created:** 2026-07-18
- **Related:** goto-line-time.md, fixed-columns-middle-elide.md

## Goal

An optional left gutter showing each line's source-row number (its absolute
position in the capture), toggled from the View menu — so a line's number is
visible while reading and matches "Go to line N".

## Scope

- **In:** a muted, right-aligned line-number gutter painted at the left of every
  row when enabled; a View toggle; persisted. Numbers are 1-based **source-model**
  rows (stable across filtering, like bookmarks/incidents).
- **Out (non-goals):** clickable gutter, per-row markers beyond the number, gutter
  in the detail pane.

## Design

The delegate paints column 0 full width starting at `x = left + self._pad`. Add a
gutter that reserves width at the far left and shifts all content right by the
same amount. The gutter width sizes to the digit count of the source model's row
count, so it's stable during a viewport of appends.

The source row for a proxy index: `index.model().mapToSource(index).row()` when
the model has `mapToSource` (it does — the view uses the proxy); the delegate
already unwraps `src` this way for other roles.

| File | Layer | Change |
|---|---|---|
| `src/zlog/ui/log_delegate.py` | ui | Add `self.line_numbers = False`. New `_gutter_w(src, fm) -> int`: `0` when off, else `fm.horizontalAdvance("0" * digits) + cw` where `digits = len(str(max(1, src.rowCount())))`. Compute a `gutter` offset once in `paint` and add it to the starting `x` for **all** paths (banner/placeholder and the segmented path). In `sizeHint` (wrap), subtract the gutter from `avail`. Paint the number right-aligned in `[left, left+gutter)` using `self._meta`/`self._sel_fg`, with a hair-line divider (`self._muted`) at the gutter's right edge. Source row for the number: unwrap the proxy index to the source row (+1). |
| `src/zlog/ui/main_window.py` | ui | `self.line_numbers_action = QAction("Line Numbers", checkable)`, in the View menu near the process/collapse toggles. `_on_line_numbers_toggled(checked)`: `self.log_delegate.line_numbers = checked`, `_apply_row_height()` (widths unchanged but keeps wrap heights honest) + `self.table.viewport().update()`. Wire `_settings_specs` (`"line_numbers"`). |
| `src/zlog/core/settings.py` | core | Add `"line_numbers": False` to `DEFAULTS`. |

The gutter offset must feed the shared `_col_widths`/`_msg_left` geometry so
Time/Tag/message all move together. Cleanest: thread the gutter into the `left`
used by `_col_widths` (treat `left + gutter` as the effective left) rather than
sprinkling `+ gutter` at each `seg`.

## Architecture touch points

- **Threading:** none.
- **Model/proxy:** none new. Reads `src.rowCount()` for width and the proxy→source
  mapping for the number; both cheap and per-visible-row only.
- **Dependency direction:** `ui` only.

## Risks & regressions to check

- Gutter width vs. wrap `sizeHint`: `avail` for the wrapped message must shrink by
  the gutter, or wrapped rows mis-measure their height. Cover with a wrapped row +
  line numbers on.
- Banner/unparsed rows (the early-return path) must also honor the gutter offset,
  or their text overlaps the numbers.
- Selected rows: number should stay legible — use `self._sel_fg` on selection,
  matching the metadata columns.
- Alignment with `goto-line`: confirm `_open_goto`'s "line N" targets the same
  source-row basis; document if it's proxy-row instead (then the gutter is still a
  useful absolute reference, note the distinction in the code comment).

## Verification

- [ ] `uv run pytest` (unit-test `_gutter_w`: off → 0; width grows with row count).
- [ ] `uv run ruff check .` and `uv run ruff format --check .`
- [ ] `run-zlog` driver scenario `line-numbers`: seed rows, toggle on, screenshot
      shows numbers; plus a wrapped variant to prove message width shrinks.

## Open questions

- Source-row vs. proxy-row numbering. Decision: **source-row** (absolute), so the
  number is stable and matches bookmark/incident indexing.
