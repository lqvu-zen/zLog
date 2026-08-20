# Plan: Multi-line bookmark notes, included in export

- **Status:** Done  <!-- Draft | Approved | In progress | Done | Abandoned -->
- **Owner:** unassigned
- **Created:** 2026-08-20
- **Related:** [bookmark-labels.md](bookmark-labels.md), [export-formats.md](export-formats.md), [pdf-export.md](pdf-export.md), [redaction-on-export.md](redaction-on-export.md)

## Goal

A note attached to a bookmarked line (`bookmark-labels.md`) survives past the
live session: it can hold more than one line, and it actually appears in
CSV/JSON/HTML/PDF export and Markdown copy — none of which include it today.

## Read this first: this extends bookmark-labels.md, it doesn't compete with it

`bookmark-labels.md` already ships the marking mechanism and storage
(`LogTableModel._bookmarks: dict[int, str]`, `core/models.py`... actually
`ui/log_model.py:68` — a source-row → label map, already persisted in session
bundles). This plan does **not** introduce a second annotation system. It closes
two concrete, verified gaps in what already exists:

1. **The note editor is single-line** — `_edit_bookmark_note`
   (`ui/main_window.py:1482`) uses `QInputDialog.getText`, so a note longer than
   one line is impossible today, even though the model already stores an
   arbitrary string. (Compare `main_window.py:2904`, which already uses
   `QInputDialog.getMultiLineText` for editing extractor patterns — same widget,
   different call site.)
2. **No export path includes it.** `core/export.py`'s `to_csv`/`to_json`/
   `to_html` (and `to_print_html` for PDF) all take a plain `entries:
   list[LogEntry]` with no row-index or bookmark context at all — confirmed by
   reading the module: zero mentions of "bookmark" anywhere in `export.py`.

## Scope

- **In:** upgrade the note editor to multi-line; thread bookmark labels through
  to CSV/JSON/HTML/PDF export and Markdown copy as an optional extra
  field/column, only for rows that have one.
- **Out (non-goals):** notes on non-bookmarked rows (bookmarking remains the
  marking mechanism — unchanged); rich text/Markdown formatting inside a note
  (plain text only, consistent with the rest of the app).

## Design

| File | Layer | Change |
|---|---|---|
| `src/zlog/ui/main_window.py` | ui | `_edit_bookmark_note` (`main_window.py:1482-1490`): swap `QInputDialog.getText` for `QInputDialog.getMultiLineText`, same pattern already used at `main_window.py:2904`. |
| `src/zlog/core/export.py` | core | **Implemented as `notes: list[str] \| None`, positionally aligned with `entries`** — not `dict[int, str]` as originally sketched. This sidesteps the index-space-mismatch risk below by construction: the caller (which already knows whether it's exporting the full or filtered view) builds the aligned list once, so `to_csv`/`to_json`/`to_html`/`to_print_html`/`to_markdown` never need to know about source rows at all. Each gains a `note` column/field only when `notes is not None`; a short `notes` list pads with `""` rather than raising (`_note_at` helper). |
| `src/zlog/ui/export_actions.py` | ui | `export_formatted`/`export_pdf` gain a `notes` parameter, redacted via a new `maybe_redact_notes` alongside the existing `maybe_redact`. |
| `src/zlog/ui/main_window.py` | ui | New `_filtered_notes()`/`_selected_notes()` (built alongside new `_filtered_source_rows()`/`_selected_source_rows()` helpers) return the aligned list, or **`None` when nothing in scope is bookmarked** (via a `_notes_or_none` helper) — so an export with zero bookmarks is byte-for-byte identical to before this feature existed, not a table with an always-empty `note` column. |
| `src/zlog/core/redact.py` | core | No change needed — `redact_text(s: str) -> str` was already public; reused directly on note strings rather than adding a new function. |
| `tests/test_export.py`, `tests/test_main_window_settings.py` | — | Notes present/absent per format; short-`notes`-list padding; redaction of note text; positional alignment across a filter change; the multi-line note editor. |

## Architecture touch points

- **Model/proxy:** none — `model.bookmarks()` already exists and is read-only
  from the export path's perspective.
- **Dependency direction:** `core/export.py` stays Qt-free; only the `ui` glue
  that calls it changes.
- **Threading:** none.

## Risks & regressions to check

- **Index-space mismatch is the real hazard.** `model.bookmarks()` returns
  `{source_row: label}`, but an export of the *filtered* view (`save_filtered_log`)
  iterates a different, smaller sequence than the master row list. **Resolved**
  by never passing a source-row-keyed dict past `main_window.py`: `_filtered_notes`/
  `_selected_notes` do the proxy→source mapping once and hand `core/export.py` a
  plain positional list, so the formatters can't get the index space wrong even
  in principle.
- **Every existing export/copy call site must be updated deliberately, or some
  formats silently keep excluding notes** while others include them — enumerate
  every caller of `to_csv`/`to_json`/`to_html`/`to_print_html`/the Markdown
  copy path before considering this done, rather than updating whichever one
  happens to be touched first.
- **`redact_on_export` interaction** must be decided, not defaulted into by
  accident — see Design table row above.
- **Multi-line note text inside CSV/JSON** must round-trip correctly (the `csv`
  module already quotes embedded newlines per RFC 4180 — confirm this rather
  than assuming; JSON handles it for free).

## Verification

- [x] `uv run pytest` — `tests/test_export.py` (note column present/absent per
      format, short-list padding, multi-line round-trip through CSV/JSON/HTML/
      Markdown/PDF-HTML) and `tests/test_main_window_settings.py`
      (`test_bookmark_notes_export_alignment`, `test_notes_or_none_helper`,
      `test_redact_toggle_drives_maybe_redact_notes`,
      `test_edit_bookmark_note_accepts_multiple_lines`) — all green.
- [x] `uv run ruff check .` / `ruff format --check .` clean on the changed files.
- [x] Manual (via `run-zlog` `bookmark-notes` scenario, screenshotted): a
      multi-line note on a bookmarked row shows first-line-plus-ellipsis in the
      Bookmarks dock, an unlabeled bookmark still falls back to its message
      preview.
- [x] Filtered-view alignment covered by
      `test_bookmark_notes_export_alignment`, which narrows the query mid-test
      and re-checks `_filtered_notes()` lines up with the row that survives.
- [x] Redaction covered by `test_redact_toggle_drives_maybe_redact_notes`.

## Open questions

- **Should the detail pane also show a bookmarked row's note** when that row is
  selected (today it doesn't appear anywhere outside the Bookmarks dock)?
  **Deferred** — left out of this pass to keep the change to what was scoped;
  worth a small follow-up plan if it comes up, since it's the same underlying
  data (`model.bookmark_label`).
- **CSV/JSON column name:** resolved as `note` (lowercase, matching `FIELDS`'
  naming), `Note` (capitalized) for the HTML/PDF column headers, matching the
  existing `FIELDS` header casing convention in each format.
