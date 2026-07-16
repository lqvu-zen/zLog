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
| [backlog.md](backlog.md) | Ideas | Candidate features to implement later (design sketches + effort) |
| [crash-anr-detector.md](crash-anr-detector.md) | Done | Recognize FATAL EXCEPTION/ANR lines; status-bar badge + next/prev incident jump |
| [time-range-filter.md](time-range-filter.md) | Done | `since:`/`until:` query tokens bound the view to a time-of-day range |
| [isolate-toggle.md](isolate-toggle.md) | Done | One-click isolate to a row's pid+tag, toggles back to the prior query |
| [persistent-highlight-rules.md](persistent-highlight-rules.md) | Done | User term/regex → color rules, always highlighted regardless of active search |
| [jank-summary.md](jank-summary.md) | Done | View → Jank Summary: Choreographer skipped-frames aggregated by PID |
| [level-full-names.md](level-full-names.md) | Done | `level:error`/`level:WARNING` etc. work like `level:E`, case-insensitive |
| [debounce-query-filter.md](debounce-query-filter.md) | Done | Fix typing lag: debounce the query bar + collapse ~9 proxy invalidates into 1 |
| [pause-follow-on-selection.md](pause-follow-on-selection.md) | Done | Auto-scroll only fires when at the bottom AND no row is selected |
| [inline-match-highlight.md](inline-match-highlight.md) | Done | Highlight the matched substring inside a row, not just the row tint (Highlight mode) |
| [goto-line-time.md](goto-line-time.md) | Done | Ctrl+G jumps to a line number or a timestamp |
| [exclude-pid-proc.md](exclude-pid-proc.md) | Done | `-pid:`/`-proc:` query negatives + right-click "Exclude PID/package" |
| [adb-connect-wifi.md](adb-connect-wifi.md) | Done | "Connect…" button runs `adb connect host:port` and refreshes devices |
| [custom-adb-path.md](custom-adb-path.md) | Done | Settings field to point zLog at a specific adb executable |
| [copy-as-html.md](copy-as-html.md) | Done | "Copy as HTML" clipboard action preserving level colors |
| [self-diagnostics-log.md](self-diagnostics-log.md) | Done | zLog logs its own behavior to a rotating zlog.log (banner, adb errors, excepthook); Help → Open Log Folder |
| [query-token-highlight.md](query-token-highlight.md) | Done | Tint recognized tokens (level:/tag:/package:/pid:/proc:/-excl//re/) in the query bar |
| [perf-start-freeze.md](perf-start-freeze.md) | Done | Debounce counts + coalesce follow-scroll so Start on a busy device doesn't freeze |
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
| [mute-tag.md](mute-tag.md) | Done | Right-click to mute a tag/PID via the exclude filter |
| [search-history.md](search-history.md) | Done | Remember recent search terms in a dropdown |
| [menu-bar.md](menu-bar.md) | Done | Restore the File/View menu bar (drop the overflow button) |
| [two-bar-header.md](two-bar-header.md) | Done | Device bar over a dedicated full-width filter row |
| [package-bar.md](package-bar.md) | Done | Restore a visible package/process selector bar |
| [log-buffers.md](log-buffers.md) | Done | Choose adb logcat buffers (main/system/crash/radio/...) |
| [clear-device-buffer.md](clear-device-buffer.md) | Done | View action: adb logcat -c to wipe the device buffer |
| [tail-count.md](tail-count.md) | Done | Start streaming from the last N lines (adb logcat -T N) |
| [level-multiselect.md](level-multiselect.md) | Done | Show only specific levels, not just a min-level floor |
| [logcat-style-ui.md](logcat-style-ui.md) | Done | Android-Studio-style dense log view: query bar + icon rail + overflow |
| [docs-sync-redesign.md](docs-sync-redesign.md) | Done | Sync GUIDE/README/CLAUDE/ARCHITECTURE + screenshots to the redesign |
| [ui-combo-selection-contrast.md](ui-combo-selection-contrast.md) | Done | Legible hover/selected text in combo-box dropdowns (both themes) |
| [log-text-contrast.md](log-text-contrast.md) | Done | Darker metadata columns + always-visible level chip on selected rows |
| [ring-buffer-cap.md](ring-buffer-cap.md) | Done | Cap the master list to the last N lines (bounded memory) |
| [clear-device-button.md](clear-device-button.md) | Done | Device-bar button to wipe the device logcat buffer (adb logcat -c) |
| [single-header-bar.md](single-header-bar.md) | Done | Device + package controls on one bar, split by a vertical divider |
| [ctrl-wheel-zoom.md](ctrl-wheel-zoom.md) | Done | Ctrl+mouse-wheel zooms the log/detail text (reuses _zoom) |
| [clear-device-clears-view.md](clear-device-clears-view.md) | Done | Clear device also empties the view so the action is visible |
| [readable-log-font.md](readable-log-font.md) | Done | Readable monospace family chain + 11pt base for the log |
| [smart-follow.md](smart-follow.md) | Done | Follow auto-pauses when you scroll up, resumes at the bottom |
| [checkbox-checked-visual.md](checkbox-checked-visual.md) | Done | Checkboxes show a filled accent box when checked (native glyph was suppressed) |
| [robust-parsing.md](robust-parsing.md) | Done | Parse threadtime/time/brief/tag formats; raw fallback for odd lines |
| [min-level-selector.md](min-level-selector.md) | Done | Visible min-level dropdown on the filter row (coexists with query level:) |
| [pause-resume.md](pause-resume.md) | Done | Pause freezes the view (adb keeps running); Resume flushes buffered lines |
| [auto-reconnect.md](auto-reconnect.md) | Done | Resume the stream after a device drop, from the last timestamp (no re-dump) |
| [export-formats.md](export-formats.md) | Done | File → Export the visible log to CSV / JSON / HTML |
| [copy-variants.md](copy-variants.md) | Done | Right-click: Copy as Markdown / Copy message only |
| [open-recent.md](open-recent.md) | Done | File → Open Recent list of recently opened/saved logs (persisted) |
| [reopen-last.md](reopen-last.md) | Done | Opt-in View toggle: reopen the most-recent log on launch |
| [session-bundles.md](session-bundles.md) | Done | Save/Open a .zsession: log + query + highlights + bookmarks together |
| [autosave-capture.md](autosave-capture.md) | Done | Opt-in autosave of live capture to disk, size-capped with one .1 rollover |
| [severity-navigation.md](severity-navigation.md) | Done | F2/Shift+F2 jump to next/prev warning-or-above line (wraps) |
| [tag-summary.md](tag-summary.md) | Done | View → Tag Summary dialog (tags by count); double-click to filter |
| [remember-splitter.md](remember-splitter.md) | Done | Persist the log/detail splitter position across launches |
| [scrollbar-heat.md](scrollbar-heat.md) | Done | Error-position ticks on the log scrollbar (debounced, bucketed) |
| [collapse-repeats.md](collapse-repeats.md) | Done | View toggle: hide consecutive duplicate lines (proxy gate) |
| [error-sparkline.md](error-sparkline.md) | Done | Status-bar sparkline of error density over the recent tail |
| [command-palette.md](command-palette.md) | Done | Ctrl+K fuzzy command palette over the menus |
| [watch-pattern.md](watch-pattern.md) | Done | Notify (tray/beep) when a captured line matches a watch pattern |
| [diff-captures.md](diff-captures.md) | Done | File → Diff Against File: unified colored diff (normalized keys) |
| [plugin-colorizers.md](plugin-colorizers.md) | Done | Load user colorize(entry) plugins to tint rows; View → Reload Plugins |
| [new-window.md](new-window.md) | Done | File → New Window: independent second window for concurrent device streams |
| [device-tabs.md](device-tabs.md) | Done | Tabbed concurrent device streams (LogSession re-rooting + tab bar) |
| [saved-filters-sidebar.md](saved-filters-sidebar.md) | Done | Left dock listing saved filter presets; Save/Delete + double-click apply |
| [preset-edit.md](preset-edit.md) | Done | Preview a saved filter (summary + tooltip); Update-to-current + Rename |
| [preset-save-full-query.md](preset-save-full-query.md) | Done | Presets store the raw query text so tag:/-exclude tokens survive save/apply |
| [level-query-sync.md](level-query-sync.md) | Done | Level dropdown ↔ query level: token stay in sync both ways |
| [process-name-column.md](process-name-column.md) | Done | Optional PID→process/package name column (adb ps + Start proc), like Android Studio |
| [auto-size-columns.md](auto-size-columns.md) | Superseded | (replaced by fixed-columns-middle-elide) |
| [fixed-columns-middle-elide.md](fixed-columns-middle-elide.md) | Done | Fixed column widths; Tag/Process middle-elide; Time kept full width |
| [message-min-half.md](message-min-half.md) | Done | Message keeps ≥50% of the row; Tag/Process shrink to fit, Time/PID/Level stay full |
| [settings-dialog.md](settings-dialog.md) | Done | Tabbed Settings dialog (top-bar entry); View menu decluttered to commands only |
| [quick-filter-pid-package.md](quick-filter-pid-package.md) | Done | Right-click Filter to… PID / Package (pid: and proc: query tokens) |
| [wrap-messages.md](wrap-messages.md) | Done | Optional multi-line wrap of long messages in the log list (Settings → Log view) |
| [level-query-