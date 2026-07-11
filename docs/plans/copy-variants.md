# Plan: Copy as Markdown / message-only copy

- **Status:** Done
- **Owner:** unassigned
- **Created:** 2026-07-11
- **Related:** ROADMAP v1.3 "Sessions & export", [copy-to-clipboard.md](copy-to-clipboard.md),
  [export-formats.md](export-formats.md)

## Goal

After this ships, the log's right-click menu can copy the selected rows two more
ways: **Copy as Markdown** (a GitHub-flavored table for pasting into issues/docs)
and **Copy message only** (just the message text — grab a stack trace or a value
without the metadata). The existing Ctrl+C threadtime copy is unchanged.

## Scope

- **In:** pure `to_markdown` + `to_messages` formatters; two context-menu actions
  wired to the clipboard, operating on the current selection.
- **Out:** copying the whole log (Export already covers that), rich-text/HTML
  clipboard, configurable columns.

## Design

| File | Layer | Change |
|---|---|---|
| `src/zlog/core/export.py` | core | `to_markdown(entries)` — header + separator + one row per entry, escaping `|`→`\|` and collapsing newlines to spaces so a message can't break the table. `to_messages(entries)` — messages joined by newlines. |
| `src/zlog/ui/main_window.py` | ui | Import the two formatters. In `_show_table_menu`, add "Copy as Markdown" and "Copy message only" after Copy. Add `_copy_markdown` / `_copy_messages` that put the formatted selection on the clipboard and report a count (reusing `_selected_entries`). |
| `tests/test_export.py` | tests | Markdown has the header/separator rows and escapes pipes; messages-only returns just the message lines. |

## Architecture touch points

- **core stays Qt-free / tested;** the UI only reads the selection and writes the
  clipboard.
- **Reuses `_selected_entries()`** — same selection semantics as Ctrl+C.

## Risks & regressions to check

- **Table-breaking content:** messages with `|` or newlines must be escaped/flattened
  in the Markdown cell.
- **Empty selection:** both actions no-op quietly (like `copy_selection`).

## Verification

- [ ] `uv run pytest` (new formatter tests)
- [ ] `uv run ruff check .` and `uv run ruff format --check .`
- [ ] Manual: select rows, both copy variants paste correctly.
