# Plan: Copy selected rows to clipboard

- **Status:** Done  <!-- Draft | Approved | In progress | Done | Abandoned -->
- **Owner:** Vũ
- **Created:** 2026-06-30

## Goal

Let the user select one or more log rows and copy them to the clipboard as text —
so a stack trace or a run of interesting lines can be pasted into a bug report,
chat, or editor.

## Scope

- **In:**
  - **Ctrl+C** copies the currently selected rows.
  - A right-click **context menu** on the table with **Copy** (and **Select All**).
  - Copied text is the same `adb logcat -v threadtime` format used by Save Log, one
    line per row, in row order.
- **Out (non-goals):** copying a single cell only; "copy as CSV/JSON"; copying the
  whole (unselected) view — Save Log already covers exporting everything.

## Design

Selection lives in the view; formatting reuses the existing `core.session`
serializer. The only new logic is mapping selected proxy rows back to source
entries, which is Qt glue in the window; the text it produces is exposed as a
method so it can be verified without touching the real clipboard.

| File | Layer | Change |
|---|---|---|
| `src/zlog/ui/main_window.py` | ui | Enable multi-row selection (already `SelectRows`; ensure `ExtendedSelection`). Add: `_selected_entries()` → the `LogEntry`s for `table.selectionModel().selectedRows()`, mapped proxy→source and returned in row order; `_selected_text()` → `entries_to_text(self._selected_entries())`; `copy_selection()` → put that text on `QApplication.clipboard()` and show "Copied N lines." Wire a `QShortcut(QKeySequence.Copy, self.table, …)` and a `customContextMenuRequested` handler that pops a `QMenu` with **Copy** (enabled when there's a selection) and **Select All**. |
| `.claude/skills/run-zlog/scripts/driver.py` | (skill) | a `copy` scenario: seed rows, select a couple via the selection model, and print `window._selected_text()` so the copied text can be verified headlessly (the offscreen clipboard isn't reliable to read back). |

## Architecture touch points

- **Threading/model:** none. Selection and copy run on the main thread; the model
  stays virtualized (we only read `entry_at` for the selected source rows).
- **Reuse:** copied text comes from `core.session.entries_to_text` — no duplicate
  formatting, and it round-trips with Open Log.
- **Dependency direction:** UI-only; `core` untouched and still Qt-free.
- **Versioning:** no bump (release-only).

## Risks & regressions to check

- Empty selection → Copy is a no-op (and disabled in the menu).
- Multi-row copy preserves top-to-bottom order regardless of click order.
- Proxy→source mapping is correct when a filter is active (copies what's visible
  and selected, not hidden rows).
- Ctrl+C works when the table has focus; doesn't clobber other shortcuts.
- Copied text pasted back parses cleanly (it's the Save Log format).

## Verification

- [x] `uv run pytest` (unchanged; `entries_to_text` already covered)
- [x] `uv run ruff check .` and `uv run ruff format --check .`
- [x] `run-zlog` `copy` scenario prints the expected threadtime text for the
      selected rows
- [ ] Manual: select rows, Ctrl+C, paste elsewhere → correct lines; right-click →
      Copy / Select All work

## Open questions

- Include **Select All** in the context menu (proposed) — or Copy only?
- Copy the raw threadtime line (proposed) vs a prettier columnar format?
