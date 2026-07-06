# Plan: Save filtered log

- **Status:** Done
- **Owner:** Vũ
- **Created:** 2026-07-01
- **Related:** completes the "save only the filtered view" non-goal in `save-load.md`

## Goal

Let the user export only the **currently visible** (filtered) lines to a `.log`
file — e.g. save just the errors you filtered to — alongside the existing full Save.

## Scope

- **In:** a **File → Save Filtered Log…** action that writes the proxy's visible rows
  (respecting level/text/regex/package filters) in the same threadtime `.log` format.
- **Out:** choosing a subset by selection (Copy already covers selection); a separate
  format.

## Design

Reuses `core.session.entries_to_text`; only the row-gathering differs (visible rows
via the proxy vs. the whole master list).

| File | Layer | Change |
|---|---|---|
| `src/zlog/ui/main_window.py` | ui | Add a **Save &Filtered Log…** action to the File menu. Factor a `_write_log(entries, default_name)` helper used by both Save actions. Add `_filtered_entries()` that maps each visible proxy row to its source `LogEntry`. `save_log` writes `model.all_entries()`; `save_filtered_log` writes `_filtered_entries()`. |

## Architecture touch points

- **Model/threading:** none. Gathering visible rows reads through the proxy on the
  main thread; the model stays virtualized.
- **Dependency direction:** UI-only; reuses pure `core.session`. `core` untouched.
- **Versioning:** no bump (next bump is the 1.1 release).

## Risks & regressions to check

- Filtered save contains exactly the visible rows, in order; full Save unchanged.
- Empty filtered view writes an empty file (no crash).
- IO errors show a message, not a crash (shared with the existing Save).

## Verification

- [ ] `uv run pytest`
- [ ] `uv run ruff check .` and `uv run ruff format --check .`
- [ ] Headless: seed rows, apply a level filter, `_filtered_entries()` returns only
      the visible ones (and matches `entries_to_text` output)
- [ ] Manual: filter to errors, Save Filtered Log, reopen → only those lines
