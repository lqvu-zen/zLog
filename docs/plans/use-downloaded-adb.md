# Plan: Explicit "use zLog's downloaded adb" option

- **Status:** Done
  <!-- Draft | Approved | In progress | Done | Abandoned -->
- **Owner:** unassigned
- **Created:** 2026-08-17
- **Related:** [bundle-adb.md](bundle-adb.md), [custom-adb-path.md](custom-adb-path.md)

## Goal

Once zLog has fetched its own managed copy of adb (`bundle-adb.md`'s "Download
for me" flow), a user whose `PATH` also has a different (older/broken/wrong)
`adb` can explicitly tell zLog to use the one it downloaded, instead of only
being able to type/paste that path by hand.

## Not bundling — see bundle-adb.md

`bundle-adb.md` already recorded, for a licensing reason (Google's platform-tools
SDK terms forbid redistribution), that zLog will never ship an `adb` binary
inside itself. This plan doesn't touch that: it's about a copy the **user
already downloaded from Google** via zLog's existing fetch flow, sitting in
their own app-data folder. Nothing new is redistributed.

## Why this is a UI gap, not a resolution-order gap

`core/adbpath.resolve_adb` already resolves `setting > PATH > managed` — so
"use the managed copy" is already fully expressible today: set the Settings
adb-path override to the managed copy's exact path. The only thing missing is
that a user has no easy way to *discover or fill in* that path — it's a
generated location under `QStandardPaths.AppDataLocation` they'd have to know
to go find. No core logic changes; this is one button.

## Scope

- **In:** a "Use downloaded copy" button in Settings' adb-path row, shown only
  when a managed copy actually exists on disk, that fills the adb-path field
  with its exact path (same mechanic as the existing "Browse…" button).
- **Out (non-goals):** any change to `resolve_adb`'s order or `bundle-adb.md`'s
  decisions; auto-switching without the user clicking Apply/OK; a way to
  *delete* the managed copy (already out of scope in bundle-adb.md too).

## Design

| File | Layer | Change |
|---|---|---|
| `src/zlog/ui/settings_dialog.py` | ui | `SettingsDialog.__init__` gains `managed_adb_path: str \| None = None`. When not `None`, add a "Use downloaded copy" `QPushButton` to `adb_path_row` (next to Browse…/Download adb…) that calls `self.adb_path_edit.setText(managed_adb_path)` — identical mechanic to `_browse_adb_path`, just a fixed path instead of a file dialog. |
| `src/zlog/ui/main_window.py` | ui | `_open_settings()` passes `managed_adb_path=self._managed_adb()` (the helper already used by `_resolve_adb`) alongside the existing `adb_effective`/`on_download_adb` kwargs. |
| `tests/test_settings_dialog.py` | — | Button present only when `managed_adb_path` given (mirrors the existing `on_download_adb` presence test); clicking it fills `adb_path_edit` with that exact path; absent when `None`. |

## Architecture touch points

- **Threading / model / dependency direction:** none — a dialog field fill,
  same shape as the existing Browse… button.

## Risks & regressions to check

- **Don't imply this is a redistribution/bundling feature** — button label and
  this plan both say "downloaded", not "built-in", to keep the licensing
  distinction visible to anyone reading the code later.
- **Only show the button when the managed copy actually exists** — a button
  that fills in a path to a file that isn't there yet would silently produce
  a broken override (the existing "Download adb…" button already covers the
  fetch-it-first case).
- **Don't regress the existing adb-path field/Browse…/Download adb… controls**
  — purely additive to the same row.

## Verification

- [x] `uv run pytest` — targeted (`test_settings_dialog.py`,
      `test_main_window_adb.py`, `test_adbpath.py`), 29/29 green; 2 new tests
      for the button (presence-only-when-given, click-fills-the-field).
- [x] `uv run ruff check .` / `ruff format --check .` — clean, repo-wide.
- [x] Manual, real `MainWindow`: with a fake managed copy on disk and a
      *different* `adb` stubbed on PATH, `_resolve_adb()` reported
      `("...other adb.exe", "path")` before; clicking "Use downloaded copy"
      then applying the dialog's values made it report
      `("...managed adb.exe", "setting")` — the override actually overrides
      PATH, not just cosmetically fills a text field.

## Open questions

None.
