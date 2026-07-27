# Feature backlog — candidate features (to implement later)

- **Status:** Ideas (each item becomes its own Approved plan when we pick it up)
- **Owner:** unassigned
- **Created:** 2026-07-14

## Status (2026-07-24)

**The backlog is empty — every remaining candidate now has its own Draft plan.**
This file stays as the place new raw ideas land before they earn a plan.

Everything previously listed here has either shipped (see the
[plans index](README.md)) or been written up:

| Was a backlog item | Now |
|---|---|
| Live file-follow (`tail -f`) | [file-follow.md](file-follow.md) |
| Windows Event Log source | [windows-event-log.md](windows-event-log.md) |
| ETW tracing | [etw-tracing.md](etw-tracing.md) |
| Persist tabs across launches | [persist-tabs.md](persist-tabs.md) |
| Theme editor | [theme-editor.md](theme-editor.md) |
| Watch action: run a command | [watch-run-command.md](watch-run-command.md) |
| Print / PDF export | [pdf-export.md](pdf-export.md) |
| Richer per-tab status | [tab-polish.md](tab-polish.md) |
| Drag-reorder tabs | [tab-polish.md](tab-polish.md) |
| Close-tab confirmation while recording | [tab-polish.md](tab-polish.md) |

## Suggested order

Not binding, but this is the order that maximizes value per unit of risk:

1. **[file-follow.md](file-follow.md)** — closes the last real gap in "debug any
   app" (apps that log to a file), and it's cross-platform, so it's fully testable
   in CI rather than only by hand on Windows.
2. **[tab-polish.md](tab-polish.md)** and **[persist-tabs.md](persist-tabs.md)** —
   small, self-contained, and they compound with the tab work already shipped.
3. **[watch-run-command.md](watch-run-command.md)**,
   **[pdf-export.md](pdf-export.md)**, **[theme-editor.md](theme-editor.md)** —
   independent conveniences, pick by appetite.
4. **[windows-event-log.md](windows-event-log.md)** — valuable but adds a
   Windows-only dependency (pywin32).
5. **[etw-tracing.md](etw-tracing.md)** — only if the cheaper sources prove
   insufficient. Deliberately last.

## Notes

New ideas go here first as a one-liner. When we pick one up, copy `TEMPLATE.md`
to a focused plan, set it **Approved**, and implement — keeping zLog's invariants
(logic in Qt-free `core/` with unit tests, UI driven via signals, model
virtualized).
