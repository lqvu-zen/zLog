# Feature backlog — candidate features (to implement later)

- **Status:** Ideas (each item becomes its own Approved plan when we pick it up)
- **Owner:** unassigned
- **Created:** 2026-07-14

## Status (2026-07-24)

The vast majority of this backlog has shipped — each picked-up idea became its
own Done plan (see the [plans index](README.md)). That now includes everything
previously parked under "Deferred": **timeline histogram**, **regex extract
fields**, **sticky header line**, and **merged multi-device view** all landed, so
that section is gone. Also shipped since the last refresh: **query-bar
autocomplete**, **filter-preset context menu + Save/Update button**, **more themes
(Solarized Dark, Monokai)**, and **open logs in a new tab** (with the tab-bar +
button).

What follows is only what's still genuinely open. When we pick one, copy
`TEMPLATE.md` to a focused plan, set it **Approved**, and implement — keeping
zLog's invariants (logic in Qt-free `core/` with unit tests, UI driven via
signals, model virtualized).

## Remaining candidates

### Analysis & export
- **Print / PDF export** (P3, M) — render the visible log to PDF (level colors
  preserved). Sketch: reuse the HTML exporter, then a print/PDF path.

### Appearance & UX
- **Theme editor** (P2, M) — a small dialog to edit `ui/theme.py` tokens and save
  a custom theme (the preset list and Solarized/Monokai already shipped; this is
  the user-editable side). Sketch: editor over `THEMES` tokens; persist a custom
  entry.

### Capture & devices
- **Richer per-tab status** (P2, S) — show paused / disconnected state and a line
  count in each tab title (the streaming `● serial` dot already ships; this adds
  the other states + count). Sketch: extend `_set_tab_label` off session state.

### Productivity / integration
- **Watch action: run a command** (P2, M) — on a watch-pattern hit, optionally run
  a shell command, not just beep/notify (sound already ships). Sketch: extend the
  watch config with an optional command + safe execution.

## Tab follow-ups (from the new-tab feature)

Explicit non-goals of `open-in-new-tab.md`, parked here as candidates:

- **Persist tabs across launches** (P2, M) — reopen the previous session's tabs
  (files + queries) on startup.
- **Drag-reorder tabs** (P3, S) — let the tab bar reorder via drag.
- **Close-tab confirmation for a live recording** (P3, S) — warn before closing a
  tab that's actively streaming.

## Notes

Most items keep zLog's invariants: put logic in Qt-free `core/` with unit tests,
drive the UI via signals, keep the model virtualized. When we pick one, copy
`TEMPLATE.md` to a focused plan, set it **Approved**, and implement.
