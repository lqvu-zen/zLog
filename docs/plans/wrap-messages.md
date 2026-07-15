# Plan: Optional multi-line (wrap) message mode

- **Status:** Done
- **Owner:** unassigned
- **Created:** 2026-07-14
- **Related:** [detail-pane.md](detail-pane.md), [logcat-style-ui.md](logcat-style-ui.md), [settings-dialog.md](settings-dialog.md)

## Goal

Optionally show the full log message wrapped across multiple lines in the log list
(instead of a single elided line), toggleable on/off with a chosen number of lines.

## Design (full variable-height wrap)

Keep the model virtualized and O(1) row sizing by using a **uniform** row height of
`wrap_lines` text lines when wrap is on (never per-row variable heights, which would
be O(all rows) in QTableView).

- `LogItemDelegate`: `wrap` + `wrap_lines`. `sizeHint` height = `lines * fm.height + 4`.
  When wrapping, metadata (time/pid/tag/level chip) paints on the first line and the
  message is word-wrapped (`Qt.TextWordWrap`, top-aligned) into the row's full height
  (clipped past `wrap_lines`; the detail pane still shows the complete text).
- `MainWindow._apply_row_height()` sets the vertical header's default section size from
  the font + wrap state (called on zoom and on toggle).
- Persisted settings `wrap` (bool) and `wrap_lines` (int); exposed in Settings → Log view
  (a checkbox + a spin box).

| File | Change |
|---|---|
| `core/settings.py` | `wrap: False`, `wrap_lines: 3` defaults. |
| `ui/log_delegate.py` | `wrap`/`wrap_lines`; `sizeHint`; wrap painting. |
| `ui/main_window.py` | `_apply_row_height`; settings specs + collect/apply; dialog wiring. |
| `ui/settings_dialog.py` | "Wrap messages" checkbox + "Wrap lines" spin. |
| tests | delegate sizeHint height; settings round-trip; dialog values. |

## Verification

- [ ] `uv run pytest`  - [ ] ruff clean
- [ ] Toggle wrap in Settings → rows grow to N lines and long messages wrap; off restores single-line.

## Update (2026-07-14)

Changed from a capped uniform N-line height to **true variable per-row height**: the
delegate's `sizeHint` computes each row's full wrapped height (reading the column
width from the view), and the table uses `ResizeToContents` when wrap is on. Dropped
the `wrap_lines` setting — just a single "Wrap messages" toggle now. Cost: sizing
rows to content is O(rows) when wrap is on (user-accepted; it's optional).

## Follow-up: wrap froze Start on a busy device (2026-07-15)

The first full-wrap implementation set the table's vertical header to
`QHeaderView.ResizeToContents`, which re-measures **every** row on every insert —
O(n²) during a fast dump. Benchmark: loading 60k lines took **39.81 s** with wrap
on vs **0.18 s** off, freezing the app on Start.

Fix: the header now stays `QHeaderView.Fixed` at all times; when wrap is on, only
the rows currently in the viewport are grown to their content via
`_fit_visible_rows()` (O(visible)), coalesced behind a 60 ms `_wrap_timer` on
inserts and on vertical-scrollbar movement. Result: 60k lines now load in **0.19 s**
with wrap on, matching wrap off, and it stays O(visible) at any buffer size.

## Follow-up: default-on, Follow lag, and clipped Time stamp (2026-07-15)

- Wrap is now **on by default** (`settings.DEFAULTS["wrap"] = True`).
- **Follow stopped keeping up in wrap mode.** `scrollToBottom()` ran before the rows
  it just revealed were grown, so it stopped short of the true bottom; the next
  batch's "were we at the bottom?" check then read false and Follow never resumed.
  `_do_follow_scroll` now scrolls, fits the now-visible rows, and re-pins to the
  bottom.
- **Last digit of the Time stamp was clipped.** The Time box was sized as
  `char_count * M-width`; per-character advance rounding left it a few px short.
  `_col_widths` now measures the actual glyph run (`fm.horizontalAdvance("0"*n)`),
  which fits the full `MM-DD HH:MM:SS.mmm` stamp on any font.
