# zLog — Live Log Viewer

One viewer for the logs you're debugging, wherever they come from: an Android
device over `adb logcat`, a Windows app's `OutputDebugString`, a program you
launch from zLog, a log file being written right now, or the Windows Event Log.
Same filters, tabs, and export for all of them.

Originally an Android logcat viewer inspired by
[plog](https://github.com/katatunix/plog). Built with **Python + PySide6 (Qt)**
and managed with **[uv](https://docs.astral.sh/uv/)**. Targets Windows first;
the code is cross-platform.

## Project layout

```
zLog/
├── pyproject.toml        # project metadata, deps, tooling config
├── uv.lock               # pinned, reproducible dependency versions
├── .python-version       # Python version for uv
├── src/
│   └── zlog/
│       ├── app.py            # entry point  → main()
│       ├── __main__.py       # enables `python -m zlog`
│       ├── cli.py            # headless `zlog --tail` mode
│       ├── core/             # pure logic, NO Qt (easy to test) — ~45 files:
│       │   ├── models.py     #   LogEntry, level ranks
│       │   ├── parser.py     #   logcat line parsing
│       │   ├── query.py      #   query-bar grammar (level:/tag:/-exclude/...)
│       │   ├── settings.py   #   load/save settings as plain JSON
│       │   ├── tabstate.py   #   what a saved tab looks like, for restore
│       │   ├── dbwin.py      #   Windows DBWIN buffer → LogEntry (pure half)
│       │   └── winevent.py   #   Windows Event Log XML → LogEntry (pure half)
│       ├── adb/
│       │   ├── reader.py     # background QThread running `adb logcat`
│       │   └── devices.py    # `adb devices` parsing, connect-over-Wi-Fi
│       ├── winlog/           # Windows-only sources, lazily imported
│       │   ├── dbwin_reader.py   # OutputDebugString capture (QThread)
│       │   ├── evtlog_reader.py  # Event Log subscription (QThread)
│       │   └── launcher.py       # launch + capture an app (QThread)
│       └── ui/                # ~35 files, Qt only
│           ├── main_window.py       # window, wiring, thin slots
│           ├── build.py             # widget construction + layout
│           ├── menus.py             # menu bar
│           ├── log_model.py         # Qt table model + filter proxy
│           ├── log_delegate.py      # one-line-per-row paint delegate
│           ├── capture_controller.py# attach/detach readers per tab
│           └── device_controller.py # device list + package/PID filter state
└── tests/
    └── test_parser.py    # unit tests for the parser (no display needed)
```

See `docs/ARCHITECTURE.md` for the full module map and the reader contract every
log source honors, and `CLAUDE.md`'s "Where things live" table for the exhaustive,
kept-current file list.

**Why this shape?** The `core` layer has no Qt imports, so it can be unit-tested
without a display and reused if the UI ever changes. `adb` and `winlog` each own
one family of streaming threads, `ui` owns everything Qt. Each concern lives in
one place, which is what makes the project easy to grow — five log sources now
share the same model/proxy/delegate stack without any of them knowing about the
others.

## Data flow

```
AdbReader / DebugOutputReader / EventLogReader / LaunchReader / FileFollower
    each a background QThread; parses its own source to LogEntry
        │  batch_ready  (signal, batched per source)
        ▼
CaptureController routes the batch to its session
        ▼
LogTableModel  ── master list of every line (virtualized)
        │
LogFilterProxy ── decides which rows show (level + tag + text + package/pid/proc + time + exclude)
        │
LogItemDelegate ─ paints one dense line per visible row (no grid)
```

Filtering is driven by a single **query bar** parsed by `core/query.py`
(`level: tag: package: pid: proc: -exclude /regex/ text`).

Three ideas make this scale to huge logs: reading happens **off the UI thread**;
the model is **virtualized** (Qt only asks for visible rows); and filtering is a
**proxy on top of the master list**, so clearing a filter is instant.

## Prerequisites

- [uv](https://docs.astral.sh/uv/getting-started/installation/) — only to run
  from source; the released `.exe` needs nothing installed.
- **For Android devices only:** `adb` (see below).
- **For Windows debug output / launching an app / following a log file:**
  nothing extra — these work out of the box.

> Note: `requires-python` is `>=3.14`. uv will fetch a matching Python for you
> automatically if you don't have one.

### Getting adb (Android only)

zLog runs `adb` to talk to Android devices. It is **not bundled** — Google's SDK
terms don't permit redistributing the platform-tools binaries — so you supply it
once. Everything that isn't an Android device works without it.

1. Download **[SDK Platform-Tools](https://developer.android.com/tools/releases/platform-tools)**
   for your OS (a ~10 MB zip; no Android Studio needed).
2. Unzip it somewhere permanent, e.g. `C:\platform-tools`.
3. Either add that folder to your **PATH**, or point zLog straight at it:
   **Settings → adb path** → browse to `adb.exe`. The Settings route avoids
   touching your system PATH.
4. Confirm with `adb version` in a terminal, then press **Refresh** in zLog —
   no restart needed.

If adb is missing, zLog says so once in the status bar and carries on: the
Windows sources (**This PC**, **Launch App…**, **Follow File…**) stay fully
usable, and any saved `.log` file still opens.

Already have Android Studio? You very likely have adb at
`%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe` (Windows) or
`~/Library/Android/sdk/platform-tools/adb` (macOS) — point Settings there rather
than downloading a second copy, so zLog and Android Studio share one adb server.

## User guide

See **[docs/GUIDE.md](docs/GUIDE.md)** for a walkthrough with screenshots.

## Roadmap

See **[docs/ROADMAP.md](docs/ROADMAP.md)** for the prioritized long-term plan.

## Run

```bash
uv run zlog
```

That's it — `uv run` creates the virtual environment, installs locked
dependencies, and launches the app. Equivalent: `uv run python -m zlog`.

Click **Start** to stream, type in the **query bar** to filter (with the **Level**
dropdown for the minimum severity), **Clear** to empty the view, **Stop** to end
streaming. Preferences live in the **Settings…** dialog on the menu bar.

## Develop

```bash
uv sync --extra dev     # install app + dev tools (pytest, ruff)
uv run pytest           # run the test suite
uv run ruff check .     # lint
uv run ruff format .    # format
```

## Build a Windows .exe

Built with [cx_Freeze](https://cx-freeze.readthedocs.io/) (run on Windows):

```bash
uv run --extra build python cxfreeze_setup.py build
```

The app lands in `build\exe.win-amd64-<pyver>\zlog.exe` (with its bundled runtime).
Or double-click **build.bat**. See the `release-zlog` skill for the full release flow.

## Features

A dense, Android-Studio-style log view with a single **query bar**
(`level: tag: package: pid: proc: -exclude /regex/ text`) and right-click
quick-filters. Highlights: a device picker with per-device **tabs** and **New
Window**; live package/PID tracking; an optional **process/package-name column**;
optional **word-wrap** to show the full message; a tabbed **Settings** dialog;
highlight mode; match and severity navigation; bookmarks; filter presets with a
**Saved Filters** sidebar; a **command palette** (Ctrl+K); relative-time display;
light/dark themes; font zoom; export (CSV/JSON/HTML); session bundles; and
save/open. See **[docs/GUIDE.md](docs/GUIDE.md)** for the walkthrough and
**[docs/ROADMAP.md](docs/ROADMAP.md)** for what's planned next.

## License

MIT — see [LICENSE](LICENSE).
