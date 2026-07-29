# Changelog

All notable changes to zLog are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/), and the project follows
[Semantic Versioning](https://semver.org/).

## [1.0.0] — 2026-07-29

First public release — a Windows-first desktop viewer for Android `adb logcat`
(and, on Windows, your own apps' console/debug output), built with Python +
PySide6 and managed with uv.

### Streaming & devices
- Live `adb logcat -v threadtime` streaming on a background thread, delivered to the
  UI in batches so it stays responsive under heavy volume; **Pause**/**Resume**
  freezes the view without stopping capture, and a dropped device **auto-reconnects**
  from the last timestamp (no re-dump).
- Device picker with **Refresh** and **Connect…** (`adb connect host:port` for
  Wi-Fi devices); remembers the last-used device across launches. Choose which
  `adb logcat` **buffers** to read (main/system/crash/radio/events/kernel) and
  whether to start from the whole buffer or the last *N* lines.
- **Clear device** wipes the on-device logcat ring buffer (`adb logcat -c`) and the
  view together.
- **Device tabs**: stream several devices concurrently, each in its own tab, plus
  **File → New Window** for a fully independent second window. A **merged view**
  can tag and combine several device streams into one, filterable with `device:`.
- Bounded memory via a configurable ring-buffer line cap.

### Windows-native sources
- Capture any Windows app's console output and `OutputDebugString` stream
  (DebugView-style), tagged by PID/process — pick **This PC** in the device box.
- **Launch App…** starts a program and captures it from its very first line
  (stdout/stderr *and* debug output), for cases you can't get by attaching after
  the fact.
- Stream **Windows Event Log** channels (Application/System/Security/…) as a
  source, alongside adb and Windows debug output.
- **Follow a log file** live (`tail -f`), including rotation/truncation, cross-platform.

### Filtering & the query bar
- A single **query bar** drives everything: `level:` `tag:` `pid:` `proc:`/`package:`
  `-exclude` `/regex/` `since:`/`until:`, with context-aware **autocomplete** (keys,
  level names, and live tag/PID/process values from the current log) and colored
  token highlighting.
- **App filter**: one **App** selector whose **Load** lists names seen in the log
  *and*, on Windows, everything currently running (the overlap marked ●); **Apply**
  filters by resolved process (`proc:`), staying in sync with the query bar. Live PID
  tracking follows the app across restarts.
- Minimum-level filter (V → F) as a dropdown in sync with `level:`, plus a
  **multi-select** mode to show only specific levels.
- Case-insensitive or case-sensitive search, with **Regex** mode (an invalid pattern
  is flagged and keeps the previous filter) and a **Highlight** mode that tints
  matches instead of hiding non-matches (find-in-log, with F3/Shift+F3 navigation).
- **Exclude** filter and negatives (`-pid:`, `-proc:`) to hide noise; right-click a
  line to mute its tag or filter/exclude by level, tag, PID, or app.
- **Isolate** toggles the view to one row's pid+tag and back; active query tokens
  render as removable **chips** under the bar.
- **Saved filter presets**: a left **Saved Filters** dock lists them; Save/Update,
  Add/Edit/Rename/Delete from the right-click menu, with a live preview.
- **Clear filters** resets everything (level, search, tag, app, time…) in one click.

### Reading & navigating logs
- Virtualized table that stays fast at millions of rows: per-level color tints,
  right-aligned PID/TID, fixed columns with middle-elide for Tag/Process, and an
  optional PID→process-name column resolved like Android Studio's logcat.
- **Row detail pane** with the full, word-wrapped message of the selected line;
  optional multi-line **wrap** for long messages in the list itself.
- **Bookmarks** (pin/jump, named, with a dock) and **crash/ANR detection** with
  status-bar badges and next/prev incident navigation.
- **Stack-trace folding** collapses a Java exception's `at …` frames under its
  header, expandable; **collapse repeated lines** shows a `×N` badge instead of
  hiding duplicates.
- Jump around fast: **Ctrl+G** to a line number or timestamp, F2/Shift+F2 to the
  next/prev warning-or-above line, jump to next/prev line sharing a tag or PID, a
  **Jank Summary** (Choreographer skipped-frames by PID), and a **Tag Summary**
  dialog.
- **Follow** (tail) toggle that auto-pauses when you scroll up and resumes at the
  bottom, never yanking the view out from under you; **Top**/**Latest** jump
  buttons independent of Follow.
- Persistent term/regex **highlight rules**, per-tag highlight colors, an
  error-density **sparkline**, and error-position ticks on the scrollbar.
- Status bar shows total and per-level counts, and a visible-of-total tally when
  filtered.

### Sessions, export & sharing
- **Save** the captured (or filtered/visible-only) log to a `.log` file and **Open**
  it offline (no device); **Open Recent**, opt-in **reopen last on launch**, and
  **restore the previous session's tabs** (files + queries) on launch.
- **Session bundles** (`.zsession`): log + query + highlights + bookmarks together
  in one file. Opt-in **autosave** of a live capture to disk, size-capped.
- **Export** the visible log to CSV / JSON / HTML / PDF; **copy** selected rows as
  plain text, HTML (preserving level colors), Markdown, or message-only.
- **Diff Against File**: a unified, colored diff between two captures.
- Opt-in **redaction** (emails/IPs/tokens masked) on save/export.
- **Capture dumpsys…** saves a one-shot device snapshot to a text file.
- **Watch** a pattern for a notification (tray/beep) or to run a command on a hit.

### Appearance & customization
- **Light** and **Dark** themes, plus a **theme editor** to tweak and save custom
  colors.
- Compact/Default/Comfortable **density** modes, a monospace **font family**
  picker, and zoom (Ctrl+=/-/0, Ctrl+wheel).
- Optional left-gutter **line numbers**; column visibility and widths persisted.
- **Ctrl+K command palette** for fuzzy access to menu commands.
- Remembers theme, window geometry, filters, tag highlights, column visibility,
  splitter position, and the detail pane across launches.

### Automation & extensibility
- Headless **CLI**: `zlog --tail --filter '<query>'` streams filtered logcat to
  stdout, no GUI.
- **Plugin colorizers**: user `colorize(entry)` scripts tint rows, reloadable from
  the View menu.
- Custom **adb path** setting, for a non-PATH `adb`.

### Project
- Python 3.14 + PySide6, managed with uv; layered architecture (`core` stays
  Qt-free and unit-tested, `ui → adb → core` one-way) with worker threads reaching
  the UI only via Qt signals. CI on GitHub Actions; MIT licensed. Self-diagnostics
  log for troubleshooting (Help → Open Log Folder); illustrated user guide in
  `docs/GUIDE.md`.

[1.0.0]: https://github.com/lqvu-zen/zLog/releases/tag/v1.0.0
