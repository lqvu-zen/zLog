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
