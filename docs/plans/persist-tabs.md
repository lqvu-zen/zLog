# Plan: Reopen tabs on launch

- **Status:** Done  <!-- Draft | Approved | In progress | Done | Abandoned -->
- **Owner:** unassigned
- **Created:** 2026-07-24
- **Related:** [open-in-new-tab.md](open-in-new-tab.md), [device-tabs.md](device-tabs.md), [reopen-last.md](reopen-last.md), [settings-persistence.md](settings-persistence.md)

## Goal

Come back to the tabs you left: on launch zLog restores the previous session's
tabs — each loaded file reopened, each tab's query and level restored — instead of
a single empty tab.

## Scope

- **In:** persist a per-tab list (file path if any, query, level, package box,
  title) on close; restore it on launch behind the existing "reopen last log"
  preference, generalized to "restore tabs". Skip entries whose file is gone.
- **Out (non-goals):** restoring **live streams** (a device or capture is a
  runtime thing — don't auto-start readers on launch), restoring in-memory
  captured lines that were never saved to a file, and cross-window restore.

## Design

`LogSession` already carries everything needed (`title`, `query`, `level`,
`package`); the settings layer already has a table-driven spec that save/restore
share. So this is one new settings key plus a restore pass.

| File | Layer | Change |
|---|---|---|
| `src/zlog/core/tabstate.py` (new) | core | Pure shaping: `TabState` (path, query, level, package); `tabs_to_json(list) -> list[dict]` / `tabs_from_json(data) -> list[TabState]` with validation (drop malformed entries, cap the count). Unit-tested. |
| `src/zlog/ui/main_window.py` | ui | Add a `tabs` entry to `_settings_specs` (the existing `(key, get, set)` table, so save and restore can't drift): **get** maps `self._sessions` → `tabs_to_json`; **set** stores the list for the post-construction restore. `_restore_tabs()` runs where `_maybe_reopen_last` does today: for each state create a tab (reusing the first, empty one), load its file via the existing `_open_log_in_tab` path, and apply its query/level. Replace the "Reopen Last Log on Launch" action with "Restore Tabs on Launch" (same settings key semantics, renamed label). |
| `docs/GUIDE.md` | — | Note that tabs come back on launch and that live captures don't auto-resume. |
| `tests/test_tabstate.py`, `tests/test_main_window_tabs.py` | — | Pure round-trip + malformed input; window: two tabs with files and queries survive a save/restore cycle; a missing file is skipped without an error dialog; a streaming tab isn't resurrected as a stream. |

## Architecture touch points

- **Threading:** none — restore is file loading, which already has the async
  large-file path; restoring several big files must not block the window.
- **Model/proxy:** none new.
- **Dependency direction:** `core/tabstate.py` is Qt-free; the window drives it.

## Risks & regressions to check

- **Slow launch:** restoring several large logs could stall startup — reuse the
  async loader and consider restoring lazily (load a tab's file when first shown).
- **Missing/moved files** must be skipped silently (or noted in the status bar),
  never a modal error per tab.
- **Interaction with `_maybe_reopen_last`:** the old single-file behaviour must
  not run *as well*, or the last log opens twice.
- **A streaming tab at exit** has no file to restore — it should come back as an
  empty tab with its query intact, not attempt to reconnect.
- Settings back-compat: an old settings file without the `tabs` key must still
  load and behave like today.

## Verification

- [ ] `uv run pytest` (round-trip, missing file, no stream resurrection)
- [ ] `uv run ruff check .` and `uv run ruff format --check .`
- [ ] Manual: open two logs in tabs, set different queries, quit, relaunch — both
      return with their queries; delete one file first and confirm it's skipped.

## Open questions

- **Cap:** **Resolved:** 10 (`core.tabstate.MAX_TABS`).
- **Lazy load:** **Resolved:** not needed yet — restore loads eagerly, reusing the
  existing async large-file path. Revisit if launch time suffers.
- **Fold in "reopen last log"?** **Resolved:** yes. The action is relabelled
  "Restore Tabs on Launch" but keeps its `reopen_last` settings key, and an old
  settings file with no `tabs` list still reopens the most recent log.
