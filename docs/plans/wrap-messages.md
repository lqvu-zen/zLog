# Plan: Optional multi-line (wrap) message mode

- **Status:** Done
- **Owner:** unassigned
- **Created:** 2026-07-14
- **Related:** [detail-pane.md](detail-pane.md), [logcat-style-ui.md](logcat-style-ui.md), [settings-dialog.md](settings-dialog.md)

## Goal

Optionally show the full log message wrapped across multiple lines in the log list
(instead of a single elided line), toggleable on/off with a chosen number of lines.

## Design (virtualization-safe: uniform row height)

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
