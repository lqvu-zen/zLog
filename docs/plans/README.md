# Plans

zLog uses **plan-first** development: before writing code for any feature, fix, or
notable change, write a plan here and get it approved. Plans are living documents —
update the status as work proceeds, and mark it Done when shipped.

## Why

A short plan front-loads the thinking that keeps zLog's invariants intact (Qt-free
`core`, one-way `ui → adb → core` deps, workers reaching the UI only via signals,
a virtualized model). It also gives a place to agree on scope before code exists,
which is cheaper than reworking a built feature.

## How to use

- **One plan per purpose.** Split a large effort into several focused files
  (e.g. `device-picker.md`, `package-filter.md`, `save-load.md`) rather than one
  giant plan. A plan should be readable in a couple of minutes.
- **Start from the template.** Copy `TEMPLATE.md` to `docs/plans/<short-slug>.md`
  and fill it in.
- **Get it approved before implementing.** The `add-zlog-feature` and
  `review-zlog-ui` skills require an approved plan before code changes.
- **Keep the status line current:** `Draft → Approved → In progress → Done`
  (or `Abandoned`, with a one-line reason).
- **Keep this index updated** — add a row when you create a plan.

For the prioritized, cross-release picture these plans execute against, see the
[project roadmap](../ROADMAP.md).

## Index

| Plan | Status | Summary |
|---|---|---|
| [device-picker.md](device-picker.md) | Done | Choose which connected device/emulator to stream from |
| [package-filter.md](package-filter.md) | Done | Filter the view to one app's process (package → PIDs) |
| [regex-search.md](regex-search.md) | Done | Match log lines with a regular expression |
| [save-load.md](save-load.md) | Done | Save the captured log to a file and reopen it offline |
| [theming-dark-mode.md](theming-dark-mode.md) | Done | Light/Dark themes with colors centralized in ui/theme.py |
| [pause-autoscroll.md](pause-autoscroll.md) | Done | Follow toggle for tail-following vs free scrolling |
| [live-pid-tracking.md](live-pid-tracking.md) | Done | Keep the package filter live across app restarts |
| [ui-column-polish.md](ui-column-polish.md) | Done | Sensible column widths; stop the Time column wrapping |
| [empty-state-and-polish.md](empty-state-and-polish.md) | Done | Empty-table placeholder + PID/TID align, row banding, button copy |
| [copy-to-clipboard.md](copy-to-clipboard.md) | Done | Copy selected rows to the clipboard (Ctrl+C, context menu) |
| [tag-highlight.md](tag-highlight.md) | Done | Assign a background color to a tag so its rows stand out |
| [settings-persistence.md](settings-persistence.md) | Done | Remember theme, window size, filters, and highlights across launches |
| [detail-pane.md](detail-pane.md) | Done | Panel showing the full wrapped text of the selected log line |
| [level-counts.md](level-counts.md) | Done | Status-bar tally of total lines and per-level counts |
| [column-visibility.md](column-visibility.md) | Done | Show/hide table columns from the View menu, persisted |
| [clear-on-start.md](clear-on-start.md) | Done | Optionally clear the log when starting a new stream |
| [save-filtered.md](save-filtered.md) | Done | Export only the currently visible (filtered) rows |
| [release-workflow.md](release-workflow.md) | Done | Automated Windows exe build & GitHub Release on v* tags |
| [clear-filters.md](clear-filters.md) | Done | Reset all filters (level, search, package) in one click |
| [remember-device.md](remember-device.md) | Done | Reselect the last-used device on relaunch |
| [case-sensitive-search.md](case-sensitive-search.md) | Done | Case-sensitive search toggle |
| [phase1-cleanup.md](phase1-cleanup.md) | Done | Pin ruff; centralize the regex-error tint |
| [refactor-main-window.md](refactor-main-window.md) | Done | Slim `main_window.py`'s `__init__` + declarative settings table |
| [tech-debt-refactor.md](tech-debt-refactor.md) | Done | Phased cleanup: UI test coverage, CI/Qt gap, duplicated adb error handling, controller extraction |
| [docs-and-deprecation-cleanup.md](docs-and-deprecation-cleanup.md) | Done | Doc sync + invalidateFilter deprecation fix |
| [jump-to-latest.md](jump-to-latest.md) | Done | Toolbar Top/Latest jump buttons, independent of Follow |
| [relative-time-column.md](relative-time-column.md) | Done | Toggle Time column: absolute / since-start / delta |
| [highlight-matches.md](highlight-matches.md) | Done | Highlight search matches instead of filtering (find mode) |
| [filter-presets.md](filter-presets.md) | Done | Save/re-apply named filter combos, persisted |
| [exclude-filter.md](exclude-filter.md) | Done | Hide lines matching an exclude term (negative filter) |
| [match-navigation.md](match-navigation.md) | Done | Step between search matches (next/prev, F3) |
| [showing-count.md](showing-count.md) | Done | Status bar shows visible-of-total when filtered |
| [bookmarks.md](bookmarks.md) | Done | Pin lines and jump between bookmarks |
| [toolbar-tidy.md](toolbar-tidy.md) | Done | Split the crowded filter row into scope + search rows |
| [font-zoom.md](font-zoom.md) | Done | Zoom log/detail text in/out (Ctrl+=/-/0), persisted |
| [mute-tag.md](mute-tag.md) | Draft | Right-click to mute a tag/PID via the exclude filter |
| [search-history.md](search-history.md) | Draft | Remember recent search terms in a dropdown |
| [level-multiselect.md](level-multiselect.md) | Draft | Show only specific levels, not just a min-level floor |
| [logcat-style-ui.md](logcat-style-ui.md) | Done | Android-Studio-style dense log view: query bar + icon rail + overflow |
| [docs-sync-redesign.md](docs-sync-redesign.md) | Done | Sync GUIDE/README/CLAUDE/ARCHITECTURE + screenshots to the redesign |
