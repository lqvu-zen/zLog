# Plan: Bookmark labels & notes

- **Status:** Approved  <!-- Draft | Approved | In progress | Done | Abandoned -->
- **Owner:** Claude
- **Created:** 2026-07-18
- **Related:** bookmarks.md, session-bundles.md, saved-filters-sidebar.md

## Goal

Give bookmarks a name/note and a left dock that lists them (line number + note or
message preview); double-clicking a bookmark jumps to it, and you can edit or
remove one from the dock — so bookmarks become navigable landmarks, not just
anonymous ticks.

## Scope

- **In:** an optional text label per bookmark; a "Bookmarks" dock (list, jump on
  double-click, Edit note…, Remove); labels persisted in the `.zsession` bundle.
- **Out (non-goals):** rich notes/multiline, bookmark colors/categories,
  persisting bookmarks in app settings (they stay session-scoped, as today).

## Design

Bookmarks today are `LogTableModel._bookmarks: set[int]` (source rows), decoration
on the Time column, with Next/Prev/Clear and `.zsession` round-trip via
`bundle.py` (`bookmarks: list[int]`). Widen the store to a mapping
`{source_row: label}` (`""` = unlabeled), keep every existing call working, add a
`bookmarksChanged` signal so the dock refreshes, and extend the bundle to carry
labels (staying back-compatible with the old list form).

| File | Layer | Change |
|---|---|---|
| `src/zlog/ui/log_model.py` | ui | `_bookmarks: dict[int, str]`. `toggle_bookmark` adds `{row: ""}` / removes. New `set_bookmark_label(row, text)` and `bookmark_label(row) -> str`. `bookmarked_rows()` → `sorted(self._bookmarks)` (keys). `set_bookmarks(rows)` accepts a `list[int]` (labels "") **or** a `dict[int,str]`. `is_bookmarked` unchanged (key check). `_enforce_cap` shifts dict keys (mirror the current set-shift). Add `bookmarksChanged = Signal()`, emitted from toggle/label/clear/set (alongside the existing `dataChanged` decoration repaint). |
| `src/zlog/core/bundle.py` | core | `make_bundle(..., bookmarks)` accepts a `dict[int,str]`; serialize as `{"bookmarks": {"12": "note", ...}}`. `parse_bundle` reads either shape: a `list[int]` → `{row: ""}`; a dict → `{int(k): str(v)}` (clamp/validate). Return `bookmarks` as a `dict[int,str]`. Bump `_VERSION` to 2 (readers stay tolerant of v1). |
| `src/zlog/ui/main_window.py` | ui | Build a `bookmarks_dock` (right side, tabbed with nothing else) like the presets dock: a `QListWidget`, and Edit note… / Remove buttons. `_rebuild_bookmarks_list()`: one item per `model.bookmarked_rows()`, text `line {src+1}  •  {label or message-preview}`, item data = source row. Double-click → jump (reuse the map-to-proxy + select + scrollTo from `_goto_bookmark`). Edit note… → `QInputDialog.getText` seeded with the current label → `model.set_bookmark_label`. Remove → `model.toggle_bookmark`. Connect `model.bookmarksChanged` → `_rebuild_bookmarks_list`. `_write_session`/`_read_session` pass/apply the dict form. A View action toggles the dock's visibility. |

## Architecture touch points

- **Threading:** none.
- **Model/proxy:** bookmark decoration + a new `bookmarksChanged` signal; no proxy
  filter change (bookmarks don't gate rows).
- **Dependency direction:** `bundle.py` stays Qt-free (dicts/JSON only). The dock
  lives in `ui` and reads the model via its public methods.

## Risks & regressions to check

- Existing `.zsession` files (v1, `bookmarks: list[int]`) must still open →
  `parse_bundle` handles the list shape.
- `_enforce_cap` (ring-buffer trim) must remap dict keys and drop out-of-range
  labels, exactly like the current set logic — cover with a cap test.
- `set_bookmarks` is called on session restore with the parsed dict; clamp keys to
  valid source rows (current code already clamps).
- Next/Prev/Clear bookmark navigation unchanged (they use `bookmarked_rows()` /
  `clear_bookmarks`, which still return/clear keys).
- Dock adds screen furniture — default it hidden (opened from View) so the window
  isn't busier by default; the presets dock precedent applies.

## Verification

- [ ] `uv run pytest` (bundle round-trip with labels; v1 list still parses;
      model label get/set; cap remap keeps labels aligned).
- [ ] `uv run ruff check .` and `uv run ruff format --check .`
- [ ] `run-zlog` driver scenario `bookmark-labels`: seed rows, bookmark two, label
      one, show the dock, screenshot.

## Open questions

- Dock side: left already holds Saved Filters. Decision: right dock for Bookmarks,
  so both can be open at once.
