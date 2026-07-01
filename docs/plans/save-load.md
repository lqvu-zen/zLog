# Plan: Save / load sessions

- **Status:** Done  <!-- Draft | Approved | In progress | Done | Abandoned -->
- **Owner:** Vũ
- **Created:** 2026-06-30
- **Related:** reuses `core/parser.parse_line`; complements `device-picker.md`

## Goal

Let the user save the captured log to a file and reopen it later **offline** — no
device or adb needed — so logs can be kept, shared, and inspected after the fact.

## Scope

- **In:**
  - **Save Log…** writes the full captured log (the model's master list) to a file.
  - **Open Log…** reads a saved file and shows it (replacing the current view),
    working with no device attached.
  - File format is **plain `adb logcat -v threadtime` text** (`.log`), so files are
    human-readable, openable in any editor, and re-parseable by the existing
    `parse_line` — round-tripping through the same code that reads live logs.
  - Reasonable behavior around an active stream and around the device-specific
    package filter (see UI behavior).
- **Out (non-goals):**
  - Saving only the *filtered* view (v1 saves everything captured; "save filtered"
    can come later).
  - A binary/JSON project format, compression, or metadata sidecars.
  - Auto-save / crash recovery.

## Design

| File | Layer | Change |
|---|---|---|
| `src/zlog/core/session.py` (new) | core | `entries_to_text(entries) -> str` (one threadtime line per entry; unparsed entries, level `""`, are written as their raw `message`); `text_to_entries(text) -> list[LogEntry]` (splits lines, reuses `parse_line`). Pure, no Qt/IO — fully testable. |
| `src/zlog/core/__init__.py` | core | export `entries_to_text`, `text_to_entries`. |
| `src/zlog/ui/log_model.py` | ui | add `all_entries() -> list[LogEntry]` (returns the master list) so Save can read it without reaching into `_rows`. |
| `src/zlog/ui/main_window.py` | ui | add a **menu bar** with **File → Open Log…** / **Save Log…** (keeps the crowded toolbar clean). `save_log()` uses `QFileDialog.getSaveFileName` + `entries_to_text`; `open_log()` uses `QFileDialog.getOpenFileName` + `text_to_entries` → `model.clear()` + `model.append_entries(...)`. |
| `tests/test_session.py` (new) | tests | round-trip (`entries → text → entries` equals original for parsed lines); unparsed/banner line survives; format shape sanity. |
| `.claude/skills/run-zlog/scripts/driver.py` | (skill) | an `opened` scenario that feeds sample threadtime text through `text_to_entries` into the model and screenshots it (proves the load path renders; no file dialog). |

### UI behavior

- **Save:** default filename like `zlog-YYYYMMDD-HHMMSS.log`; writes UTF-8. Empty log
  is allowed (writes an empty file). IO error → status-bar message, no crash.
- **Open:** if a stream is running, **stop it first** (opening is an offline view),
  then clear and load. Also **clear the package (PID) filter** on open, since PIDs
  belong to the previous live device session; keep level/text filters. Status:
  `Loaded 1234 lines from <name>`.
- **Menu** entries have standard shortcuts (Ctrl+O / Ctrl+S).

## Architecture touch points

- **Threading:** file read/write is quick for typical logs and runs on the main
  thread. *Risk/fallback:* a very large file (hundreds of MB) could block briefly;
  noted as a future async-load plan, out of scope here.
- **Model:** loading uses `clear()` + `append_entries(...)` — the same virtualized
  path the live reader uses (no per-row widgets, master list stays the source of
  truth). Save reads via the new `all_entries()` accessor.
- **Dependency direction:** serialization is pure `core/session.py`; `QFileDialog`
  and file IO live in `ui`. One-way (`ui → core`) preserved; `core` stays Qt-free.
- **Round-trip integrity:** `parse_line` uses flexible whitespace, so reconstructed
  lines re-parse to equal `LogEntry` values; unparsed lines keep their raw text.
- **Versioning:** no version bump (versions change only at release).

## Risks & regressions to check

- Round-trip fidelity: a parsed entry → text → `parse_line` yields an equal entry.
- Unparsed/banner lines (level `""`) survive a round-trip as their raw text.
- Open while streaming stops the reader cleanly (no thread left running).
- Loaded view respects current level/text filters; package filter is cleared on open.
- Save/Open IO errors (permissions, bad path) show a message instead of crashing.
- Large file load stays responsive enough (virtualized model); note if not.

## Verification

- [x] `uv run pytest` (new `test_session.py` green)
- [x] `uv run ruff check .` and `uv run ruff format --check .`
- [x] `run-zlog` `opened` scenario screenshot shows a log loaded from text
- [ ] Manual: Save a live capture, Clear, Open the file → same lines appear offline
- [ ] Manual: Open a file while streaming → stream stops, file loads

## Open questions

- Save **all captured lines** (proposed) vs only the current filtered view?
- Format: **threadtime `.log` text** (proposed, interoperable) vs JSON?
- **Menu bar** for Open/Save (proposed) vs more toolbar buttons?
- On Open while streaming: **auto-stop** (proposed) vs refuse until stopped?
