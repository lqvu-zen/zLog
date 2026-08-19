# Changelog

All notable changes to zLog are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/), and the project follows
[Semantic Versioning](https://semver.org/).

## [1.3.0] — 2026-08-17

### Added
- **A real app icon.** zLog's window, taskbar, and the built `.exe` all used
  Qt's generic default icon until now.
- Settings' adb-path row gained a **Use downloaded copy** button — if zLog has
  already fetched its own adb for you but a different one on `PATH` is
  winning, this lets you explicitly point at the one zLog downloaded instead
  of typing the path by hand.

## [1.2.0] — 2026-08-17

### Added
- **User-defined log formats.** zLog no longer requires a logcat-shaped line to
  give you real fields: **View → Log Formats…** opens an editor to define a
  named regex (with `time`/`pid`/`tid`/`level`/`tag`/`message` groups) and a
  level-alias map for your own project's log, with a live preview against
  pasted sample lines. Opening a file that matches a configured format
  **auto-detects** it — no manual picking — and each tab remembers its own
  format independently. Once matched, the Level dropdown, `level:`/`tag:`,
  colors, and every other field-aware feature work on that format exactly like
  they do on logcat.
- **Export/Import** your custom formats as a `.json` file from the same
  dialog, to back them up or hand a working format to a teammate.
- The status bar now notes when an opened log came back with **no format
  recognized**, so an unparsed file doesn't look identical to a normal one.

## [1.1.1] — 2026-08-02

### Fixed
- **zLog no longer requires adb to use the Windows sources.** In 1.1.0,
  `refresh_devices()` returned early when adb couldn't be resolved, so **This
  PC** never appeared in the device picker and Start stayed disabled — the
  Windows debug-output/Event Log/Launch-App capture flow was unreachable
  without Android platform-tools installed, even though none of it needs adb.
- A capture reader (`AdbReader`, Windows debug-output, Event Log, Launch App,
  or file-follow) that was stopped in the narrow window right after starting
  could, rarely, keep running instead of actually stopping.

### Added
- If adb is missing, zLog now offers to **fetch and install platform-tools**
  for you (scoped to when you're actually picking an Android device), instead
  of only pointing you at a manual download.

### Changed
- Retitled the app window from "Android Log Viewer" to **"Live Log Viewer"**,
  reflecting that Windows capture doesn't need Android at all.
- Settings' adb-path field no longer clips long paths, and the cold-start
  status bar is quieter about adb resolution.
- The device bar's minimum width dropped from 1671px to 1561px so the window
  is usable on smaller displays; a local source's tab now shows a readable
  name ("This PC") instead of the raw internal serial.

## [1.1.0] — 2026-07-31

### Log view
- Segment labels: a thin header strip above the log names each part of the
  dense one-line rows ("Time · PID·TID · Tag · [Process] · L · Message"),
  always pixel-aligned with the rows themselves.
- **Auto-hiding columns**: the PID·TID and Tag segments collapse to no
  reserved space when a capture never populates them (Windows debug-output and
  Launch App captures never set a thread id; a followed plain-text file may
  have neither) — and reappear the moment a row actually has the data. A pid
  without a tid now shows just the pid, not a bare trailing dash.

### Devices & App filter
- **Refresh** now selects a device that just got connected (or a phone that
  just got authorized) over whatever was previously remembered — no more
  manually reselecting it from the dropdown after plugging in.
- Fixed a real `adb devices` race: right after the daemon (re)starts, or right
  after a device finishes USB enumeration, the very first call could come back
  empty — Refresh now retries once before giving up, instead of showing an
  empty device list.
- **Launch App…** remembers the last program/arguments/working directory
  across restarts, not just within the current session.

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

[1.3.0]: https://github.com/lqvu-zen/zLog/releases/tag/v1.3.0
[1.2.0]: https://github.com/lqvu-zen/zLog/releases/tag/v1.2.0
[1.1.1]: https://github.com/lqvu-zen/zLog/releases/tag/v1.1.1
[1.1.0]: https://github.com/lqvu-zen/zLog/releases/tag/v1.1.0
[1.0.0]: https://github.com/lqvu-zen/zLog/releases/tag/v1.0.0
