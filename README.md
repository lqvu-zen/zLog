# zLog — Android Log Viewer

A desktop GUI for viewing Android `adb logcat`, inspired by
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
│       ├── core/             # pure logic, NO Qt (easy to test)
│       │   ├── models.py     #   LogEntry, level ranks
│       │   └── parser.py     #   logcat line parsing
│       ├── adb/
│       │   └── reader.py     # background QThread running `adb logcat`
│       └── ui/
│           ├── log_model.py  # Qt table model + filter proxy
│           └── main_window.py# window, toolbar, wiring
└── tests/
    └── test_parser.py    # unit tests for the parser (no display needed)
```

**Why this shape?** The `core` layer has no Qt imports, so it can be unit-tested
without a display and reused if the UI ever changes. `adb` owns the streaming
thread, `ui` owns everything Qt. Each concern lives in one place, which is what
makes the project easy to grow.

## Data flow

```
AdbReader (background thread)
    runs `adb logcat -v threadtime`, parses each line
        │  batch_ready  (signal, ~50 lines at a time)
        ▼
LogTableModel  ── master list of every line (virtualized)
        │
LogFilterProxy ── decides which rows show (level + tag + text + package/pid/proc + exclude)
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
