# Changelog

All notable changes to zLog are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/), and the project follows
[Semantic Versioning](https://semver.org/).

## [1.0.0] — 2026-07-01

First stable release — a Windows-first desktop viewer for Android `adb logcat`,
built with Python + PySide6 and managed with uv.

### Streaming & devices
- Live `adb logcat -v threadtime` streaming on a background thread, delivered to the
  UI in batches so it stays responsive under heavy volume.
- Device picker with **Refresh**; streams from the selected device (`adb -s <serial>`)
  and handles `offline` / `unauthorized` states.

### Filtering & search
- Minimum-level filter (V → F).
- Case-insensitive text search over tag + message, with a **Regex** mode (an invalid
  pattern is flagged and keeps the previous filter).
- **Package filter**: resolves a package to its PID(s); **live PID tracking** follows
  the app across restarts.

### Reading logs
- Virtualized table that stays fast at millions of rows, with per-level color tints
  and right-aligned PID/TID.
- **Row detail pane** showing the full, word-wrapped message of the selected line.
- **Per-tag highlight colors** (right-click a row).
- **Follow** (tail) toggle; status bar shows total line count and per-level counts.
- Show/hide table columns from **View → Columns**.

### Sessions & appearance
- **Save** the captured log to a `.log` file and **Open** it offline (no device).
- **Copy** selected rows (Ctrl+C or right-click), in `logcat` text format.
- **Light** and **Dark** themes.
- Remembers theme, window geometry, filters, tag highlights, column visibility, and
  the detail pane across launches.

### Project
- Python 3.14 + PySide6, managed with uv; layered architecture with a Qt-free,
  unit-tested `core`; CI on GitHub Actions; MIT licensed. Illustrated user guide in
  `docs/GUIDE.md`.

[1.0.0]: https://github.com/lqvu-zen/zLog/releases/tag/v1.0.0
