# zLog User Guide

zLog is a desktop viewer for Android `adb logcat`. It streams your device's logs
into a fast, dense, one-line-per-entry view — with a single query bar to filter
down to what matters — and can save a capture to read later. This guide walks
through everyday use.

## Before you start

1. Install [Android platform-tools](https://developer.android.com/tools/releases/platform-tools)
   and make sure `adb` is on your PATH (run `adb version` to check).
2. Connect a device with **USB debugging** enabled, or start an emulator.
3. Launch zLog:

   ```bash
   uv run zlog
   ```

## The window at a glance

- A **device bar** holds the **Device** dropdown and the stream controls:
  ↻ refresh, ▶ start, ■ stop, ✕ clear, a **Follow** toggle, and ⭱ / ⭳ to jump to
  the oldest / newest line.
- Below it, a **filter bar** holds the **query bar** on its own full-width row.
- The **File** and **View** menus at the top hold themes, save/open, zoom, bookmarks,
  presets, and more.
- The **log view** shows one line per entry — `time  pid-tid  tag  ▮level  message`
  — with each level in its own color (I green, D blue, W amber, E/F red).

![Streaming logs](images/guide-streaming.png)

## Streaming logs

Pick your device from **Device** (press ↻ if it isn't listed yet), then click ▶.
Logs stream in live, newest at the bottom.

- **Follow** (on by default) keeps the view pinned to the newest line. Turn it off
  to scroll back through history without being pulled to the bottom; ⭱ / ⭳ jump to
  the oldest / newest line at any time.
- ✕ clears the view; ■ ends streaming.

## Filtering with the query bar

Type in the **query bar** to narrow the view. Terms combine — a line must match all
of them. Bare words match the tag or message; prefixes target a field:

| Type this | To… |
|---|---|
| `timeout` | show lines whose tag or message contains "timeout" |
| `level:E` | show only Error and above (V D I W E F) |
| `tag:Activity` | show only lines whose tag contains "Activity" |
| `package:com.example` | show only that app's process (resolved to its PID on the device) |
| `-GnssHal` | **hide** lines matching this term (repeatable, e.g. `-Gnss -Sensors`) |
| `/Skipped \d+ frames/` | match a **regular expression** |
| `"two words"` | quote to include spaces |

Example — errors from one tag, hiding noise:

```
level:E tag:Activity -Gnss
```

![Filtering with the query bar](images/guide-query.png)

An invalid regex tints the query bar and keeps your previous filter. The status bar
shows how many lines are visible (e.g. *Showing 8 of 26 lines*) plus a per-level
tally. Press **Clear filters** (in the **View** menu) or empty the query to show everything.

Filtering by tag or any field works the same way:

![Filter by tag](images/guide-tag.png)

## Highlight instead of hide

Prefer to keep every line visible and just *highlight* the matches? Turn on
**View → Search options → Highlight matches**. Use **F3 / Shift+F3** to jump
between matches.

## Themes

Switch between **Light** and **Dark** from **View → Theme**.

![Light theme](images/guide-light.png)

## Reading, bookmarking, and zoom

- Select a line to see its full, word-wrapped text in the detail pane.
- **Ctrl+B** bookmarks the selected line (a colored marker appears);
  **Ctrl+F2 / Ctrl+Shift+F2** jump between bookmarks (**View** menu).
- **Ctrl+= / Ctrl+- / Ctrl+0** zoom the text in, out, and back to default.
- **Time display** (**View** menu) switches the timestamp between absolute, elapsed
  since the first line, and delta from the previous line.

## Saving and reopening logs

From the **File** menu:

- **Save Log…** (Ctrl+S) writes everything captured to a `.log` file in the standard
  `logcat` text format — readable in any editor. **Save Filtered Log…** writes only
  the lines currently visible.
- **Open Log…** (Ctrl+O) loads a saved file to read offline, with no device attached.
  Opening a file stops any live stream first.

## Filter presets

Save a query you use often via **View → Filter Presets → Save current filter
as…**, then re-apply it any time from the same menu. Presets persist across launches.

## Troubleshooting

- **"adb not found"** — install platform-tools and add `adb` to your PATH.
- **No devices listed** — check the USB cable/authorization dialog on the phone,
  then press ↻. `adb devices` in a terminal should sho