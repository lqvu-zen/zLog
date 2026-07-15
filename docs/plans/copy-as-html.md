# Plan: Copy as HTML / rich text

- **Status:** Done
- **Owner:** unassigned
- **Created:** 2026-07-15
- **Related:** [copy-variants.md](copy-variants.md), [export-formats.md](export-formats.md), backlog.md

## Goal

A "Copy as HTML" context-menu action puts the selected rows on the clipboard as
rich text, so pasting into Slack/Docs/an email keeps each line's level color
instead of flattening to plain text.

## Scope

- **In:** one new context-menu action next to the existing Copy / Copy as
  Markdown / Copy message only, reusing `core.export.to_html` for the markup and
  writing both an HTML and a plain-text clipboard representation (so a
  plain-text-only paste target still gets something readable).
- **Out (non-goals):** a settings toggle for which colors/theme the exported HTML
  uses (it already uses `to_html`'s fixed light palette, same as file export);
  copying the whole log (Export already covers that) — this is selection-only,
  matching the other Copy variants.

## Design

| File | Layer | Change |
|---|---|---|
| `src/zlog/ui/main_window.py` | ui | `_show_table_menu`: add "Copy as HTML" after the existing Copy variants. `_copy_html()` calls `to_html(self._selected_entries())`, builds a `QMimeData` with `setHtml(html)` and `setText(to_messages(entries))` (plain-text fallback), and puts it on `QApplication.clipboard()` via `setMimeData` (the other Copy variants use `clipboard().setText`, which only ever writes plain text — this is the reason a `QMimeData` object is needed here). Reuses `_selected_entries()`, matching Copy/Copy as Markdown's selection semantics. |

## Architecture touch points

- No `core` change — `to_html` already exists and is unit-tested for file export;
  this only adds a clipboard path for it.
- UI-only change, no threading, no model/proxy touch.

## Risks & regressions to check

- Empty selection: no-op, matching the other Copy variants (no empty clipboard write).
- `to_html` already escapes all field text — no injection risk pasting into a
  rich-text target.
- Confirm the plain-text fallback (`setText`) is present so pasting into a
  plain-text field (e.g. a terminal) doesn't paste raw HTML tags.

## Verification

- [x] `uv run pytest` (existing `to_html` tests already cover the formatter; no
      new core logic needed — a thin UI smoke test on `_copy_html` wiring is enough)
- [x] `uv run ruff check .` and `uv run ruff format --check .`
- [x] Headless smoke: app renders with no regressions (`run-zlog` driver)

## Open questions

- None blocking.
