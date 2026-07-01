# Plan: Row detail pane

- **Status:** Done  <!-- Draft | Approved | In progress | Done | Abandoned -->
- **Owner:** Vũ
- **Created:** 2026-07-01
- **Related:** builds on `settings-persistence.md` (persists the panel's visibility)

## Goal

Show the **full, word-wrapped text** of the selected log line in a panel below the
table, so long messages (stack traces, big JSON) are readable and easy to copy —
the Message column elides them today.

## Scope

- **In:**
  - A read-only detail panel under the table, in a vertical splitter so the user can
    resize it.
  - It shows the current row's fields (time, PID/TID, level, tag) plus the **full
    message, wrapped**; text is selectable/copyable.
  - **View → Show details** toggles it; visibility is remembered across launches.
- **Out (non-goals):** rich formatting/syntax highlighting of the message; editing;
  showing multiple selected rows (just the current one).

## Design

| File | Layer | Change |
|---|---|---|
| `src/zlog/core/settings.py` | core | add `"show_details": True` to `DEFAULTS`. |
| `src/zlog/ui/main_window.py` | ui | Put the table + a read-only `QPlainTextEdit` (`self.detail`, word-wrap on) in a `QSplitter(Qt.Vertical)`. Connect the table selection's `currentRowChanged` (or `selectionChanged`) to `_update_detail()`, which maps the current proxy row to its source `LogEntry` and renders a compact header + the full message. Add a checkable **View → Show details** action bound to `self.detail.setVisible`. Load/save its state in `_load_and_apply_settings` / `_save_settings`. |
| `.claude/skills/run-zlog/scripts/driver.py` | (skill) | a `details` scenario: seed rows, select the long-message row, screenshot the populated panel. |

### Detail text format

```
Time  06-30 12:34:56.220    PID 1287  TID 1342    E  AndroidRuntime

FATAL EXCEPTION: main
    at com.example... (full message, wrapped)
```

## Architecture touch points

- **Threading/model:** none. Selection → `_update_detail` runs on the main thread and
  only *reads* the current entry via `entry_at`; the model stays virtualized.
- **Dependency direction:** UI-only, plus one new key in the pure `core/settings.py`
  `DEFAULTS`. `core` stays Qt-free.
- **Layout:** the splitter replaces the plain `addWidget(self.table)`; the toggle
  hides/shows the panel without tearing down the table.
- **Versioning:** no bump (release-only).

## Risks & regressions to check

- Selecting a row updates the panel; clearing selection empties it gracefully.
- Long messages wrap and scroll inside the panel (don't stretch the window).
- Hiding the panel reclaims space; the toggle state persists across launches.
- Existing features unaffected: virtualized scrolling, copy, highlight, filters.
- Empty/banner rows (no tag/level) render sensibly in the panel.

## Verification

- [x] `uv run pytest` (settings tests still green with the new default)
- [x] `uv run ruff check .` and `uv run ruff format --check .`
- [x] `run-zlog` `details` screenshot shows the panel with a full wrapped message
- [ ] Manual: select rows → panel updates; toggle off/on; reopen → state remembered

## Open questions

- Place the panel at the **bottom** (proposed) vs the right side?
- Default **visible** (proposed) or hidden until first toggled?
