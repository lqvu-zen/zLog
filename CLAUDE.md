# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code
in this repository. It is the load-bearing summary to read before touching the
code; deeper rationale lives in `docs/ARCHITECTURE.md`, plans live in `docs/plans/`,
and the actual workflows live in `.claude/skills/` (`add-zlog-feature`,
`review-zlog-ui`, `run-zlog`, `release-zlog`).

zLog is a **Windows-first desktop GUI for viewing Android `adb logcat`**, inspired
by [plog](https://github.com/katatunix/plog). Built with **Python + PySide6 (Qt)**,
managed with **uv**. The code is intentionally cross-platform.

## Plan first — always

Before writing code for any feature, fix, or notable change, write or update a plan
in `docs/plans/` and get it approved. One plan per purpose; split a large effort
into several focused files (e.g. `device-picker.md`, `package-filter.md`) rather
than one giant plan. Copy `docs/plans/TEMPLATE.md` to `docs/plans/<slug>.md`, keep
its status line current (Draft → Approved → In progress → Done), and only implement
once it's approved. The `add-zlog-feature` and `review-zlog-ui` skills enforce this.
See `docs/plans/README.md`.

**Before starting any new work, check `docs/plans/` for pending plans first.** Scan
`docs/plans/README.md` (or `grep -n 'Status' docs/plans/*.md`) for anything still in
**Draft**, **Approved**, or **In progress** and surface it. If an open plan matches
the request, resume it instead of creating a new one; only start a new plan once
nothing pending blocks the work.

## Commands

```bash
uv sync --extra dev          # set up virtualenv with app + dev tools
uv run zlog                  # launch the GUI (also: python -m zlog)
uv run pytest                # run all tests
uv run pytest tests/test_parser.py::test_parses_standard_threadtime_line  # single test
uv run ruff check .          # lint
uv run ruff format .         # format
```

Headless screenshot of the running UI (no physical display required):
```bash
uv run --with pillow python .claude/skills/run-zlog/scripts/driver.py smoke
# → .claude/skills/run-zlog/screenshots/*.png
```

Build the Windows executable (cx_Freeze) — see the `release-zlog` skill:
```bash
uv run --extra build python cxfreeze_setup.py build   # or double-click build.bat
# → build/exe.win-amd64-<pyver>/zlog.exe
```

Ruff is configured with `line-length = 100` and rules `E, F, I, UP, B`.

## Entry points

- Console script: `zlog` → `zlog.app:main` (in `pyproject.toml`).
- Module form: `python -m zlog` → `src/zlog/__main__.py`.
- No shim/flat script; all code lives under `src/zlog/`.

## Where things live

| Concern | File |
|---|---|
| `LogEntry`, `LEVEL_RANK`, severity `rank` | `src/zlog/core/models.py` |
| logcat line parsing (`parse_line`) | `src/zlog/core/parser.py` |
| `adb logcat` streaming thread (`AdbReader`) | `src/zlog/adb/reader.py` |
| Qt table model, filter proxy | `src/zlog/ui/log_model.py` |
| one-line-per-entry paint delegate | `src/zlog/ui/log_delegate.py` |
| query-bar parser (`level: tag: package: -exclude /regex/`) | `src/zlog/core/query.py` |
| device picker + package/PID filter state (`DeviceController`) | `src/zlog/ui/device_controller.py` |
| color themes (Light/Dark) + palette tokens | `src/zlog/ui/theme.py` |
| main window, query bar, device bar, menus, wiring | `src/zlog/ui/main_window.py` |
| headless-Qt test setup (`offscreen` qapp fixture) | `tests/conftest.py` |
| `QApplication` bootstrap (`main`) | `src/zlog/app.py` |
| `__version__` | `src/zlog/__init__.py` |
| deps, scripts, tooling config | `pyproject.toml` |
| unit tests | `tests/` |
| plans (write one before coding) | `docs/plans/` |

## Architecture

Three layers map to three packages:

**`core/`** — Pure Python, zero Qt imports. `models.py` defines `LogEntry` (frozen
dataclass) and `LEVEL_RANK` (V/D/I/W/E/F → int for `>=` comparisons). `parser.py`
exposes `parse_line(line) -> LogEntry` matching the `adb logcat -v threadtime`
format; unrecognized lines (banners, etc.) come back with empty fields and the raw
text in `message`, so nothing is silently dropped. This layer is the only one with
unit tests.

**`adb/`** — `AdbReader` is a `QThread` that runs `adb logcat -v threadtime` in a
subprocess, reads it line-by-line, and emits `batch_ready(list[LogEntry])` in
chunks of 50 (`_BATCH_SIZE`). Batching prevents high-volume logs from flooding the
Qt event loop. Stopped by setting `_running = False` and calling `proc.terminate()`.

**`ui/`** — Two Qt model classes, a paint delegate, a controller, plus the window.
The log is presented **Android-Studio-style**: one dense line per entry (no grid),
driven by a single **query bar**. The header is a **device bar** (device + stream
controls) over a full-width **filter row**; **File**/**View** menus hold the rest.
- `LogTableModel(QAbstractTableModel)` — virtualized master list; the view only
  calls `data()` for visible rows, so rendering stays cheap even at millions of rows.
  Exposes `Qt.UserRole` (the `LogEntry`) and `HIGHLIGHT_ROLE` (tag/search highlight)
  for the delegate.
- `LogFilterProxy(QSortFilterProxyModel)` — gates rows by min level, a substring/regex
  over `tag + message` (case-insensitive by default), a **tag** contains, a **package**
  PID set, and an **exclude** matcher — all without mutating the master list.
- `LogItemDelegate` (`log_delegate.py`) — paints one line per row: colored level chip,
  monospace `time  pid-tid  tag  ▮level  message`, per-level text color. Keeps the model
  virtualized (runs only for visible rows). Column visibility was retired with the grid.
- `DeviceController(QObject)` — owns the device list, remembered serial, and package/PID
  filter state (no widgets), so device selection, filtering, and live PID tracking are
  unit-testable without a `MainWindow`.
- `MainWindow` — wires `AdbReader.batch_ready` → `LogTableModel.append_entries`, the
  device-bar buttons to start/stop/clear/scroll, and the **query bar** (`_apply_query` →
  `core.query.parse_query`) to the proxy gates. Auto-scrolls only when at the bottom.

## Architecture rules that always apply

The invariants. Most "looked fine, broke in practice" bugs come from violating one.

- **Plan first.** No code without an approved plan in `docs/plans/` (see
  "Plan first — always" above).
- **`core/` must never import Qt.** Keep it that way so tests run without a display.
  New Qt-free logic (e.g. PID→process-name mapping) belongs in `core/`; anything
  needing a `QObject` belongs in `adb/` or `ui/`.
- **Dependency direction is one-way: `ui` → `adb` → `core`.** Never import
  `zlog.ui.*` from `core` or `adb` — it creates cycles and couples data to widgets.
- **Worker threads never touch widgets directly.** `AdbReader` reaches the UI only
  via signals (`batch_ready`, `error`), delivered by Qt on the main thread. Any new
  background work does the same: work off-thread, emit a signal, update widgets in
  the slot. This is the single most important rule.
- **Keep the model virtualized.** Append via `append_entries`
  (`beginInsertRows`/`endInsertRows`); never `beginResetModel` just to add lines,
  and never build a widget per row.
- **Filter through the proxy, not the master list.** Keep `_rows` complete so
  clearing a filter is instant.
- **Preserve reader→UI batching** (`_BATCH_SIZE`) when changing the read loop.
- **Comments explain WHY, not WHAT.**
- **Version bumps happen only on release.** Don't change `__version__`
  (`src/zlog/__init__.py`) or `version` (`pyproject.toml`) per feature or fix —
  bump them only when cutting a release.

## Environment notes

- `requires-python = ">=3.14"`. uv reads `.python-version` (3.14) and will fetch a
  matching interpreter automatically if you don't have one.
- The live app needs Android **platform-tools** (`adb`) on PATH and a connected
  device/emulator. The parser/filter tests need neither.
