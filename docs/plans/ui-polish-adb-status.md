# Plan: UI review — Settings adb-path label & cold-start status message

- **Status:** Done  <!-- Draft | Approved | In progress | Done | Abandoned -->
- **Owner:** unassigned
- **Created:** 2026-07-31
- **Related:** [bundle-adb.md](bundle-adb.md), [usable-without-adb.md](usable-without-adb.md)

## Goal

A user opening **Settings → Capture** can actually read which adb is in use
(the path doesn't get cut off mid-word), and a user launching zLog cold sees a
status-bar message that's about *their* log, not the app's internal plugin
count.

## Findings
**Screens reviewed:** idle/empty window, populated table (Light + Dark),
Warning-level filter, no-match filter, device picker, auto-hide columns
before/after, header strip with Process+wrap, row detail pane, Settings
dialog (all 4 tabs), the adb-setup prompt. **Screenshots:**
`smoke-idle.png`, `populated.png`, `dark.png`, `filtered-warn-and-above.png`,
`no-match.png`, `devices.png`, `auto-hide-columns-before.png`,
`auto-hide-columns-after.png`, `header-process-and-wrap.png`, `details.png`,
`settings-capture.png`, `adb-setup-prompt.png` (all in
`.claude/skills/run-zlog/screenshots/`).

### High

#### H1. Settings → Capture's "Currently using" adb path clips mid-word
- **Screen / location:** Settings dialog, Capture tab —
  `src/zlog/ui/settings_dialog.py:161-163` (the `adb_effective` row added in
  the bundle-adb.md work)
- **What & why:** The row is built as a plain `QLabel(f"{path}  ({...})")`
  with no word-wrap, placed in a `QFormLayout` whose field column is
  narrower than the label's natural width. A realistic Windows adb path
  (`C:\Users\Admin\AppData\Local\Android\Sdk\platform-tools\adb.EXE`, the
  exact path Android Studio installs to) plus the `(found on PATH)` suffix
  measures 462px but only gets ~389px — Qt clips the overflow at the widget
  boundary instead of wrapping or eliding, so the text is cut off mid-parenthesis
  (`...adb.EXE  (fo`). This is the one place the dialog tells the user which
  adb it resolved to (Settings override / PATH / a fetched copy) — precisely
  the information `bundle-adb.md` added this row to surface — and it's
  unreadable for what's a very ordinary install path, not an edge case.
- **Recommendation:** give the label (`settings_dialog.py:164`, currently
  constructed inline and discarded) a name, call `.setWordWrap(True)` on it
  before `capture.addRow(...)`, and `.setToolTip(path)` for the rare case it's
  long even wrapped. Wrapping is zero layout risk — `QFormLayout` rows already
  vary in height by content.
- **Screenshot:** `settings-capture.png`

### Medium

#### M1. Cold-start status message is an internal detail, and it clobbers a more relevant one
- **Screen / location:** `src/zlog/ui/main_window.py:1768-1777`
  (`_load_plugins`), called from `__init__` right after `_maybe_reopen_last()`
  (`main_window.py:258-259`)
- **What & why:** `_load_plugins()` unconditionally calls
  `self.statusBar().showMessage(...)` with `"Loaded 0 colorizer plugin(s)
  from <path>."` — plugin colorizers are an opt-in power-user feature
  (`docs/plans/plugin-colorizers.md`), so "0 loaded" is the common case and
  isn't something a typical user needs to know at launch. Worse, because it
  runs *after* `_maybe_reopen_last()` in `__init__`, it silently overwrites
  whatever more useful message reopening a previous session just set (e.g.
  "Loaded 1,204 lines from last-session.log") on every single cold start.
  The self-diagnostics log (`core/applog.py`) already records this same
  detail for anyone troubleshooting plugins, so the status bar isn't the only
  place it's captured.
- **Recommendation:** Only call `showMessage` when there's something to
  report: `if colorizers or errors: self.statusBar().showMessage(msg)`.
  Silence in the common (0 plugins, no errors) case leaves whatever the
  reopen-last flow (or the plain empty-state) already showed intact.
- **Screenshot:** `smoke-idle.png` (bottom-left status text)

### What already works well
- The empty and no-match states are both handled with a specific, actionable
  hint ("No logs yet — pick a device and press Start, or open a saved log
  (File → Open)." / "No lines match the current filters.") rather than a
  blank table — don't touch this pattern.
- Level-to-color mapping is consistent and legible in **both** Light and Dark
  (verified via `dark.png`): the chip background, the row text tint, and the
  letter itself all agree, so severity reads even without color (heuristic
  #3's color-blind check holds).
- The auto-hide/show column-header work (`auto-hide-columns-before/after.png`)
  is solid — labels track exactly which segments the delegate actually
  reserves space for, tested against both a no-tag/no-tid source and one that
  gains a tag mid-stream.
- The `header-process-and-wrap.png` screenshot confirms the header strip stays
  pixel-aligned with the Process column when it's toggled on — no drift.
- The adb-setup prompt (`adb-setup-prompt.png`) is clear, plain-language, and
  orders its three choices sensibly (fetch → self-install → dismiss) — no
  changes recommended.
- The device bar is dense (~20 controls on one row) but stays visually
  subordinate to the table (the bar + filter row together are a small
  fraction of window height) and has already been through several dedicated
  passes (`two-bar-header.md`, `toolbar-tidy.md`, `single-header-bar.md`) —
  not re-litigating that here.

### Deferred
- **Dark theme's top-chrome widgets rendered stale under the headless
  `run-zlog` driver** (menu bar/tab bar/device bar staying in Light colors
  after `apply_theme("Dark")`) turned out to be a driver-only artifact, not
  an app bug: the widgets' actual computed palette was already correct
  (`#1e1e1e`), it just hadn't repainted its offscreen backing store by the
  time the old 10-iteration settle loop grabbed it. Fixed directly in
  `.claude/skills/run-zlog/scripts/driver.py`'s `_shot()` (bumped to 25
  iterations) as part of this review, since it's tooling, not `src/zlog/ui/*`,
  and confirmed by re-shooting `dark.png` clean afterward. No app-side finding.
- **`scenario_columns` in the driver referenced `_column_actions`**, an
  attribute retired when column-visibility was replaced by the auto-hide
  header strip (`column-header-labels.md`, `auto-hide-empty-columns.md`).
  Removed as dead code (same driver.py edit) rather than carried forward —
  nothing in the current app exposes per-column show/hide anymore, so there
  was nothing left to fix it *into*.
- **The device bar's density** (heuristic #1/#2) is real but not new, and
  already deliberately iterated on in three prior plans (see "what already
  works well" above) — flagging that it's still dense, but not proposing a
  fourth pass without a specific complaint driving it.

## Scope

- **In:** H1 (word-wrap the adb-path label) and M1 (only show the plugin
  status message when it says something).
- **Out (non-goals):** Re-designing the Settings dialog's Capture tab layout;
  re-litigating device-bar density; anything under Deferred above.

## Design

| File | Layer | Change |
|---|---|---|
| `src/zlog/ui/settings_dialog.py` | ui | The "Currently using" `QLabel` (line 164): name it, `.setWordWrap(True)`, `.setToolTip(path)`. |
| `src/zlog/ui/main_window.py` | ui | `_load_plugins` (line ~1774-1777): guard `statusBar().showMessage(msg)` behind `if colorizers or errors:`. |

## Architecture touch points

- **Threading:** none — both changes are synchronous UI-construction/status
  calls on the main thread.
- **Model/proxy:** none.
- **Dependency direction:** unchanged; both changes stay within `ui`.

## Risks & regressions to check

- H1: word-wrapping must not visibly shift the other rows in the Capture tab
  in a jarring way — a two-line label is a normal `QFormLayout` occurrence,
  but confirm the dialog doesn't need a taller minimum height bump too.
- M1: don't accidentally suppress the message when there *are* plugins loaded
  or a plugin failed to load — those are exactly the informative cases to
  keep. Verify both branches (0-and-clean vs. some-loaded vs. errors).
- Confirm `_maybe_reopen_last()`'s own status message (when it fires) now
  survives to be seen, instead of being overwritten a frame later.

## Verification

- [x] Targeted tests (`tests/test_settings_dialog.py` — including a new
      `test_adb_effective_label_wraps_and_has_tooltip`; new
      `tests/test_main_window_plugins.py` covering silent/loaded/error
      branches) — 17 + existing suite all passed (93 passed in the
      `test_settings_dialog.py` + `test_main_window_settings.py` run before
      the new plugin test file, 17 in the two new/touched files after).
      Full-suite run deferred to a release/QA pass, not per-fix.
- [x] `uv run ruff check .` and `uv run ruff format --check .` — clean,
      whole repo.
- [x] Re-shot `settings-capture` — the path + source now wraps onto a second
      line, fully readable, no clipping.
- [x] Re-shot `smoke` — status bar now reads "0 device(s) found." (the
      picker's own message) instead of the plugin line.
- [x] Test: `test_loaded_plugin_reports_in_status_bar` and
      `test_plugin_load_error_reports_in_status_bar` cover the
      still-informative branches directly (a real relaunch-with-a-plugin
      manual check would exercise the same code path).

## Open questions

- None — both fixes are small and don't need a design decision from the user
  beyond approving the plan.
