# Plan: Regex search mode

- **Status:** Done  <!-- Draft | Approved | In progress | Done | Abandoned -->
- **Owner:** Vũ
- **Created:** 2026-06-30
- **Related:** builds on the existing text filter in `LogFilterProxy`

## Goal

Let the user match log lines with a regular expression, not just a plain
substring — e.g. `Exception|ANR`, `com\.example\.\w+`, `^Skipped \d+ frames`.

## Scope

- **In:**
  - A **Regex** checkbox next to the search box. Off = current case-insensitive
    substring behavior (unchanged). On = the search text is a regex matched against
    `tag + message`.
  - Case-insensitive matching in both modes (matches today's behavior).
  - Graceful handling of an invalid/partial regex while typing: don't crash, keep
    the previous valid filter, and signal the error (tint the box + status hint).
  - Regex combines (AND) with the existing min-level and package/PID filters.
- **Out (non-goals):**
  - A separate case-sensitivity toggle (always case-insensitive for now).
  - Regex over individual columns (still matches the combined `tag + message`).
  - Saved/named searches.

## Design

| File | Layer | Change |
|---|---|---|
| `src/zlog/core/search.py` (new) | core | `compile_matcher(text: str, regex: bool) -> Callable[[str], bool]`. Empty text → matches all. `regex=True` → `re.compile(text, re.IGNORECASE)`, predicate does `pattern.search(s)`. `regex=False` → case-insensitive substring. Raises `re.error` on an invalid pattern. Pure, testable. |
| `src/zlog/ui/log_model.py` | ui | `LogFilterProxy` holds a `_matcher` (default = match-all from `compile_matcher("", False)`). Replace `set_text` with `set_search(text, regex) -> bool`: builds the matcher via `compile_matcher`; on `re.error` returns `False` and keeps the previous matcher (view stays stable); on success stores it, calls `invalidateFilter`, returns `True`. `filterAcceptsRow` calls `self._matcher(tag + " " + message)`. |
| `src/zlog/ui/main_window.py` | ui | Add a **Regex** `QCheckBox` after the search box. A single `_apply_search()` handler (wired to `search.textChanged` and the checkbox `toggled`) calls `proxy.set_search(text, regex)` and reflects the result: clear tint + status on success, red tint + "Invalid regex — showing previous match." on failure. |
| `src/zlog/core/__init__.py` | core | export `compile_matcher`. |
| `tests/test_search.py` (new) | tests | substring match; regex match; case-insensitivity (both modes); empty → matches all; invalid regex raises `re.error`. |
| `.claude/skills/run-zlog/scripts/driver.py` | (skill) | A `regex-search` scenario: seed rows, `proxy.set_search("Exception|Skipped", regex=True)`, screenshot the matched subset. |

## Architecture touch points

- **Threading:** none — pure filtering on the main thread. The regex is compiled
  once per change (in `set_search`), not per row; `filterAcceptsRow` just calls the
  cached predicate.
- **Model/proxy:** the canonical "swap the text predicate" extension. Master list
  (`_rows`) stays complete, so toggling regex or clearing the box is instant.
- **Dependency direction:** matching logic lives in pure `core/search.py`, imported
  by the `ui` proxy — one-way (`ui → core`) preserved and keeps it unit-testable.
- **Colors/theme:** the invalid-regex tint is a small inline style for now; when a
  `ui/theme.py` exists (per the roadmap), move that color into it.
- **Versioning:** no version bump (versions change only at release).

## Risks & regressions to check

- Invalid/partial regex never crashes; previous filter stays; box tint + hint show.
- Clearing the box (empty text) shows everything again, in both modes.
- Turning Regex off restores plain-substring behavior for the same text.
- Regex ANDs correctly with min-level and package/PID filters.
- Case-insensitivity holds in both modes.
- Existing text-filter behavior is unchanged when the box is off.

## Verification

- [x] `uv run pytest` (new `test_search.py` green)
- [x] `uv run ruff check .` and `uv run ruff format --check .`
- [x] `run-zlog` `regex-search` scenario screenshot shows only matching rows
- [ ] Manual: type a valid regex → matches update; type an invalid one → red tint,
      view unchanged; toggle Regex off → substring behavior returns

## Open questions

- Checkbox label: **"Regex"** (proposed) vs ".*"?
- On invalid regex: **keep previous filter + tint** (proposed) vs blank the view?
- Case sensitivity: **always case-insensitive** (proposed) vs add a toggle later?
