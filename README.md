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
LogFilterProxy ── decides which rows show (min level + text search)
        │
QTableView     ── only renders the rows currently on screen
```

Three ideas make this scale to huge logs: reading happens **off the UI thread**;
the model is **virtualized** (Qt only asks for visible rows); and filtering is a
**proxy on top of the master list**, so clearing a filter is instant.

## Prerequisites

- [uv](https://docs.astral.sh/uv/getting-started/installation/) installed.
- [Android platform-tools](https://developer.android.com/tools/releases/platform-tools)
  on your PATH (run `adb version` to confirm).
- A device with USB debugging on, or a running emulator.

> Note: `requires-python` is `>=3.14`. uv will fetch a matching Python for you
> automatically if you don't have one.

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

Click **Start** to stream, use **Min level** and the search box to filter,
**Clear** to empty the view, **Stop** to end streaming.

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

## Where to go next

The layered structure makes these additive, not invasive:

- **Device picker** — parse `adb devices`, pass the serial to `AdbReader`.
- **Package/PID filter** — map PID → process name to show only your app.
- **Save / load** — serialize the master list; reopen offline logs.
- **Per-tag colors** and a regex search mode (extend `LogFilterProxy`).
- **Pause-autoscroll** toggle in the toolbar.

## License

MIT — see [LICENSE](LICENSE).
