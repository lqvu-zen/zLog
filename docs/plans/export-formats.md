# Plan: Export to CSV / JSON / HTML

- **Status:** Done
- **Owner:** unassigned
- **Created:** 2026-07-11
- **Related:** ROADMAP v1.3 "Sessions & export", [save-load.md](save-load.md),
  [save-filtered.md](save-filtered.md)

## Goal

After this ships, File → Export writes the current (visible) log to **CSV**, **JSON**,
or **HTML** — structured data for spreadsheets/tools, and a standalone,
level-colored HTML page for sharing — alongside the existing `.log` text save.

## Scope

- **In:** pure `core/export.py` formatters (`to_csv`, `to_json`, `to_html`); a File →
  Export submenu (CSV/JSON/HTML) that saves the currently-visible entries.
- **Out:** copy-as-Markdown / message-only copy (separate v1.3 items), session
  bundles, autosave, choosing columns.

## Design

| File | Layer | Change |
|---|---|---|
| `src/zlog/core/export.py` | core | `FIELDS = [time,pid,tid,level,tag,message]`. `to_csv` (header + rows via `csv`), `to_json` (list of dicts, `indent=2`), `to_html` (standalone doc: `<style>` with per-level row classes + an escaped `<table>`). Pure, no Qt/IO. |
| `src/zlog/ui/main_window.py` | ui | Import the formatters. Add a File → **Export** submenu (CSV/JSON/HTML); each calls `_export(name, formatter, ext)` which runs a Save dialog, writes `formatter(self._filtered_entries())`, and reports count — mirroring `_write_log`'s error handling. Exports the visible set (all rows when unfiltered). |
| `tests/test_export.py` | tests | CSV has the header + one row per entry and escapes commas; JSON round-trips to a list of dicts with the right keys; HTML escapes `<>&`, includes a per-level class, and is a full document. |

## Architecture touch points

- **core stays Qt-free / unit-tested;** the UI only picks a path and writes bytes.
- **Reuses `_filtered_entries()`** so "export" matches "what you see" (== all when
  no filter is active).

## Risks & regressions to check

- **Escaping:** CSV fields with commas/quotes/newlines (use `csv`); HTML must escape
  `< > &` so a log message can't break the page.
- **Empty log:** exporting zero entries writes a valid empty CSV (header only) /
  `[]` JSON / an empty table — no crash.

## Verification

- [ ] `uv run pytest` (new `test_export.py`)
- [ ] `uv run ruff check .` and `uv run ruff format --check .`
- [ ] Manual: export a small capture to each format and open it.
