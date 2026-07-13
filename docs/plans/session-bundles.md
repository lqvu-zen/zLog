# Plan: Session bundles (log + filters + bookmarks)

- **Status:** Done
- **Owner:** unassigned
- **Created:** 2026-07-11
- **Related:** ROADMAP v1.3 "Sessions & export", [save-load.md](save-load.md),
  [bookmarks.md](bookmarks.md), [tag-highlight.md](tag-highlight.md)

## Goal

After this ships, File → **Save Session** writes one `.zsession` file holding the
log **plus** the query, tag highlights, and bookmarks; **Open Session** restores
all of it at once — so you can hand off or return to a full investigation, not
just raw lines.

## Scope

- **In:** a JSON session format (`core/bundle.py`, pure); File menu Save/Open
  Session; restore query, tag highlights, and bookmarks alongside the log.
- **Out:** device/stream state, theme/font (those are app-wide settings), autosave
  (separate item), embedding into recents.

## Design

| File | Layer | Change |
|---|---|---|
| `src/zlog/core/bundle.py` | core | `make_bundle(log_text, query, tag_highlights, bookmarks) -> str` (JSON, `version: 1`). `parse_bundle(text) -> dict` — tolerant: normalizes to `{log:str, query:str, tag_highlights:{str:str}, bookmarks:[int]}`, ignoring bad types; JSON errors propagate to the caller. |
| `src/zlog/ui/log_model.py` | ui | `set_bookmarks(rows)` — replace the bookmark set from an iterable, clamped to valid source rows, then repaint. |
| `src/zlog/ui/main_window.py` | ui | Import the bundle fns. File → **Save Session…** / **Open Session…**. `_write_session(path)` gathers `entries_to_text(all)`, `query.text()`, `model.tag_colors()`, `model.bookmarked_rows()`. `_read_session(path)` parses, then (like Open) stops any stream, clears the PID filter, reloads the log, restores the query (`setText` → `_apply_query`), re-applies tag colors, and `set_bookmarks`. |
| `tests/test_bundle.py`, `tests/test_main_window_settings.py` | tests | Bundle round-trips + tolerates junk; a write→read cycle through the window restores query, highlights, and bookmarks. |

## Architecture touch points

- **core/bundle.py is Qt-free / tested;** the UI gathers widget/model state and
  applies it back.
- **Reuses** `entries_to_text`/`text_to_entries`, `model.tag_colors`/`set_tag_color`,
  and bookmark APIs — no new log path.

## Risks & regressions to check

- **Malformed/old files:** `parse_bundle` must not crash on missing keys or wrong
  types; a non-JSON file reports an error and leaves the view intact.
- **Bookmark indices:** clamp to the loaded log's row count so a stale index can't
  point out of range.
- **Restore order:** load the log first (so bookmark rows exist), then query, then
  highlights/bookmarks.

## Verification

- [ ] `uv run pytest`
- [ ] `uv run ruff check .` and `uv run ruff format --check .`
- [ ] Manual: bookmark + filter + highlight a capture, Save Session, reopen it.
