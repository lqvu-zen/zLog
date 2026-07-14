# Plan: A proper Settings/Preferences dialog

- **Status:** Done
- **Owner:** unassigned
- **Created:** 2026-07-14
- **Related:** [settings-persistence.md](settings-persistence.md), [menu-bar.md](menu-bar.md)

## Goal

Collect the preference toggles currently scattered across the View menu into one
readable, categorized **Settings** dialog, opened from a top-bar "Settings…" entry
after File and View. Declutter the View menu (keep only commands/navigation there).

## Design

- **`ui/settings_dialog.py` (new):** `SettingsDialog(QDialog)` — a `QTabWidget`
  (Appearance / Log view / Capture / Behavior) of plain form controls. Pure view:
  takes the current values + option lists, returns the chosen values via
  `get_values()`. No MainWindow coupling → unit-testable.
- **MainWindow:** a menu-bar `Settings…` action → `_open_settings()`. It gathers
  the current state (`_collect_settings`), shows the dialog, and on OK applies the
  result (`_apply_settings_values`) by driving the *existing* backing actions/widgets
  (so all live effects + persistence keep working), then `_save_settings()`.
- **Declutter (phase 2):** move the preference items (theme, show details, clear on
  start, reopen last, autosave, show process names, collapse, search options, time
  display, log buffers, start-from, buffer limit) out of the View menu; keep their
  backing `QAction`s as standalone state objects. Commands stay in View (clear
  filters, problems nav, tag summary, watch, reload plugins, presets, bookmarks,
  zoom, clear device buffer).

| Setting | Backing object |
|---|---|
| Theme | `_theme_group` / `apply_theme` |
| Font size offset | `_font_delta` / `_apply_font` |
| Show detail pane | `details_action` |
| Time display | `_time_actions` |
| Highlight matches | `highlight_action` |
| Case-sensitive | `case_action` |
| Collapse repeats | `collapse_action` |
| Show process names | `process_action` |
| Log buffers | `_buffer_actions` |
| Start from (tail) | `_tail_actions` |
| Buffer limit | `_max_rows_actions` |
| Clear on start | `clear_on_start_action` |
| Follow | `follow_check` |
| Reopen last | `reopen_last_action` |
| Autosave | `autosave_action` |

## Verification

- [ ] `uv run pytest` (+ dialog get_values test; apply round-trips through MainWindow)
- [ ] ruff clean
- [ ] Manual: Settings… opens; changing values and OK applies + persists.
