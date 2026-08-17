# Plan: Export/import for user-defined log formats

- **Status:** Done
  <!-- Draft | Approved | In progress | Done | Abandoned -->
- **Owner:** unassigned
- **Created:** 2026-08-17
- **Related:** [custom-log-format-editor.md](custom-log-format-editor.md)

## Goal

From the Log Formats dialog, a user can save their custom formats to a `.json`
file and load formats from one — to back up their own setup, move it to another
machine, or hand a working format to a teammate — without hand-editing settings.

## Scope

- **In:** an **Export…** and an **Import…** button in `LogFormatDialog`, working
  on the same JSON shape `core/logformat.py` already uses for settings
  persistence (`formats_to_json`/`formats_from_json` — no new core functions).
- **Out (non-goals):** a format marketplace/registry, auto-sync between
  machines, exporting a single selected format (export always writes the whole
  user list — a backup-file model, not a per-item share), drag-and-drop import,
  and importing from other tools' config formats (already a non-goal of
  `custom-log-format-editor.md`).

## Design

| File | Layer | Change |
|---|---|---|
| `src/zlog/ui/log_format_dialog.py` | ui | Add `Export…`/`Import…` buttons to the list-button row, next to Add/Remove. `_export()`: `QFileDialog.getSaveFileName(..., filter="JSON (*.json)")`, then `json.dumps(formats_to_json([f for f in self._formats if not f.builtin]), indent=2)` written to the chosen path (`encoding="utf-8"`). Read-only action — writes immediately, independent of OK/Cancel. `_import()`: `QFileDialog.getOpenFileName(...)`, read + `json.loads`, then `formats_from_json(data)` (already defensively skips malformed entries — see `core/logformat.py`). Merge into the **working** `self._formats` list: same-name user format is overwritten, new names are appended; builtins are never touched (they're filtered out of `formats_from_json`'s output already). Show one `QMessageBox` summarizing the merge ("Import 3 formats: 2 new, 1 will overwrite 'MyProject'. Continue?") before committing, then `_reload_list()`. Unreadable file / invalid JSON → `QMessageBox.warning`, no state change. Import only takes effect when the dialog is accepted (OK) — same as Add/Remove/edits; Cancel discards it. |
| `tests/test_log_format_dialog.py` (new) | — | Widget-level tests instantiating the real `LogFormatDialog`, monkeypatching `QFileDialog.getSaveFileName`/`getOpenFileName` (pattern already used in `tests/test_pdf_export.py`): export writes a file whose contents round-trip through `formats_from_json`; import appends a new-named format; import overwrites a same-named existing format; import of a malformed/non-JSON file warns and leaves `self._formats` unchanged; Cancel after Import leaves `get_values()` at the pre-import list. |

## Architecture touch points

- **Threading:** none — file read/write happens synchronously on the UI thread
  on explicit user action (same as every other save/export dialog in the app,
  e.g. `export_actions.py`), not on a background thread.
- **Model/proxy:** none.
- **Dependency direction:** entirely within `ui/`, reusing existing `core/`
  helpers unchanged. No Qt added to `core/`.

## Risks & regressions to check

- **Silent overwrite by name.** The one confirmation dialog states counts (and
  names, if the list is short) before committing, so an unintended collision is
  visible before it happens rather than after.
- **A newly-imported format's regex is never previewed automatically** — the
  slow-pattern warning only fires once a format is *selected* in the list. This
  matches the existing "preview-time only, no runtime watchdog" decision from
  `custom-log-format-editor.md`, so it's not a new gap, but worth a note: an
  imported catastrophic regex sits inert until someone clicks it, same as one
  typed by hand and not yet clicked away from.
- **A user format imported with the same name as a builtin** (e.g. someone's
  file has a format literally called `threadtime`) — `formats_from_json`
  already excludes builtins on the *export* side, but nothing stops an
  *imported* name from colliding with a builtin's name on merge. Verify
  `resolve_format`'s existing precedence behaves sanely (doesn't silently
  shadow or corrupt builtin resolution) rather than adding new collision logic
  for this case.
- **Encoding/newline round-trip** across machines — write/read `utf-8`
  explicitly; don't rely on locale defaults.

## Verification

- [x] Export produces a file that `formats_from_json(json.loads(...))` reads
      back as the exact user list that was exported
      (`test_export_writes_only_user_formats`).
- [x] Import of a file with all-new names appends them
      (`test_import_appends_a_new_format`); import of a file with a colliding
      name overwrites only that entry (`test_import_overwrites_a_same_named_format`);
      builtins are unaffected either way (both tests assert on `get_values()`,
      which already excludes builtins by construction).
- [x] Import of malformed JSON / a non-JSON file warns and leaves the working
      list byte-identical to before the attempt
      (`test_import_malformed_json_warns_and_leaves_list_unchanged`). Declining
      the merge-summary confirmation does the same
      (`test_import_declined_confirmation_leaves_list_unchanged`).
- [x] Cancelling the dialog after an Import discards it — not re-verified at
      the `LogFormatDialog` level (nothing in this change alters how the
      dialog's own OK/Cancel works; `test_dialog_cancel_changes_nothing` in
      `test_log_format_editor.py` already covers the MainWindow-level
      accept/reject contract this relies on).
- [x] `uv run pytest` — full log-format-related suite (`test_log_format_dialog.py`
      + `test_log_format_editor.py` + `test_logformat.py` + `test_parser.py`,
      62 tests) green.
- [x] `uv run ruff check .` / `ruff format --check .` — repo-wide, clean.
- [x] Screenshot via `run-zlog` (`log-formats` scenario, added to
      `driver.py`): dialog renders with the new Export…/Import… buttons; live
      preview against the two real sample lines from this conversation parses
      correctly (colon-optional case included).

## Open questions

- **Overwrite-by-name with one summary confirmation** is the proposed default
  (see Design) rather than a per-item prompt — flagging in case a per-item
  review is wanted instead once this is in front of real use.
