# Plan: Print / PDF export

- **Status:** Done  <!-- Draft | Approved | In progress | Done | Abandoned -->
- **Owner:** unassigned
- **Created:** 2026-07-24
- **Related:** [export-formats.md](export-formats.md), [copy-as-html.md](copy-as-html.md), [redaction-on-export.md](redaction-on-export.md)

## Goal

Save the visible (filtered) log as a **PDF** — level colors preserved, paginated —
for attaching to a bug report or sharing with someone who doesn't have zLog.

## Scope

- **In:** **File → Export → PDF…** renders the currently filtered rows to a PDF
  with a small header (source, capture time, active query) and page numbers;
  honours the existing redaction toggle.
- **Out (non-goals):** a print-preview dialog with layout controls, printing to a
  physical printer (near-free once this exists, but not the goal), embedding
  bookmarks/detail panes, and exporting the un-filtered master list.

## Design

`core/export.py` already produces styled **HTML** (`to_html`, reused by copy-as-
HTML). Qt can render HTML straight to PDF via `QTextDocument.print_(QPdfWriter)`,
so this is mostly wiring — no new rendering engine, and the colors come from the
same place the view uses.

| File | Layer | Change |
|---|---|---|
| `src/zlog/core/export.py` | core | `to_print_html(entries, *, title, query, theme)` — the existing HTML plus a document header and print-friendly CSS (monospace, small font, repeating table header, page-break-inside: avoid). Pure and unit-tested (assert the header and a level color appear). |
| `src/zlog/ui/main_window.py` | ui | `export_pdf()`: `QFileDialog.getSaveFileName` → build entries from the **proxy** (visible rows, redacted if the toggle is on, exactly like the other exports) → `QTextDocument.setHtml(...)` → `QPdfWriter` + `QTextDocument.print_()`. Add it to the existing Export submenu. Large captures render on the UI thread — cap or warn (see risks). |
| `docs/GUIDE.md` | — | Add PDF to the export list, noting it exports what's visible. |
| `tests/test_export.py` | — | `to_print_html` includes the query/title header, keeps level colors, escapes HTML in messages, and is empty-safe. |

## Architecture touch points

- **Threading:** rendering a big document is synchronous and can take seconds —
  either cap the row count with a warning, or (if it's slow in practice) move the
  document build off-thread and print on the main thread. Start with the cap.
- **Model/proxy:** read through the **proxy** so "what you see is what you export",
  consistent with Save Filtered Log and the other exporters.
- **Dependency direction:** HTML generation stays in Qt-free `core/`; only the
  PDF writing is `ui/`.

## Risks & regressions to check

- **Size:** a million-row capture would produce an absurd PDF and a long freeze.
  Cap (e.g. 50k rows) with a clear warning offering to narrow the filter first.
- **HTML escaping** — log lines contain `<`, `&`, and quotes; the existing
  exporter escapes, but the new header (which embeds the *query*) must too.
- **Redaction** must apply exactly as it does for other exports, or a PDF could
  leak what CSV/HTML masks.
- **Fonts:** the log is monospace; confirm the PDF embeds/falls back sensibly so
  columns don't wander.
- Reuse `to_html`'s styling rather than duplicating colors, so themes stay in one
  place.

## Verification

- [x] `uv run pytest` (print-HTML header/colors/escaping/empty; PDF page count/pagination)
- [x] `uv run ruff check .` and `uv run ruff format --check .`
- [ ] Manual: export a filtered capture, open the PDF, confirm colors, pagination,
      the header showing the query, and that redaction masked what it should.

## Resolved

- **Row cap:** 50k (`PDF_ROW_CAP` in `main_window.py`), with a
  `QMessageBox.question` offering to export just the first N lines; cancel
  aborts before the save dialog even opens.
- **Orientation/page size:** landscape A4, as leaned.
- **"Print…":** left out — the non-goal already excluded it, and there's no
  signal it's wanted; `write_pdf` could feed a `QPrintDialog`-selected
  `QPrinter` later since both are `QPagedPaintDevice`, with no rework needed.
- **Theme param dropped:** `to_print_html` doesn't take a `theme` — print output
  always uses `to_html`'s fixed light-background palette regardless of the
  active UI theme (a dark PDF page is not what "export for a bug report" wants).

## Implementation notes

- `core/export.to_print_html` adds a small header (title/generated
  time/line count/query) and `page-break-inside: avoid` on rows to the
  existing `to_html` table. `generated` is an optional override so tests are
  deterministic.
- `ui/pdf_export.write_pdf(html, path)` does the actual pagination: Qt's HTML/
  CSS support has no `@page`/`counter()`, so `QTextDocument.print_()` alone
  can't add a footer. Instead it lays the document out once, then per page
  translates + clips the painter to that page's slice and draws contents, then
  stamps "Page N of M" in a reserved footer strip — the standard Qt
  QPainter-loop pattern for this. Returns the page count for the status-bar
  message.
- `MainWindow._export_pdf` reads through the **proxy** (`_filtered_entries()`)
  and applies `_maybe_redact`, exactly like the other exporters.
