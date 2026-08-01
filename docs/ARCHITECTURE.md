# zLog Architecture

This document explains *how zLog is put together and why*. `CLAUDE.md` is the quick
reference — the authoritative "where things live" table and the rules that always
apply — and stays current with every change; this document is the reasoning behind
it, and goes stale faster because prose drifts in a way a table doesn't. If the two
ever disagree, trust `CLAUDE.md` and treat this as needing a refresh. Read this one
before making a structural change (new layer, new threading path, new data source).

## Goals that shape the design

1. **Stay responsive under heavy log volume.** `adb logcat`, a chatty Windows debug
   stream, or a fast-growing log file can all emit thousands of lines per second.
   The UI must never stutter or freeze.
2. **Be testable without a display.** Core logic (parsing, filtering rules, query
   parsing, settings, tab persistence) should run under CI/pytest with no Qt
   platform and no device attached.
3. **Be easy to extend with a new log source.** zLog started as an `adb logcat`
   viewer and now has five independent sources (Android, Windows debug output,
   Windows Event Log, a launched app, a followed file). Adding a sixth should mean
   writing one reader that honors an existing contract, not touching everything.

Every decision below serves one of these.

## The four layers

```
┌──────────────────────────────────────────────────────────┐
│  ui/        QApplication, MainWindow, LogTableModel,       │  Qt widgets
│             LogFilterProxy, LogItemDelegate,               │
│             DeviceController, CaptureController             │
└───────────────┬───────────────────────────┬───────────────┘
                │ depends on                │ depends on
┌───────────────▼───────────────┐  ┌────────▼───────────────┐
│  adb/    AdbReader (QThread)    │  │  winlog/  DebugOutputReader,│  Qt threading +
│          subprocess: adb logcat │  │           EventLogReader,   │  ctypes/pywin32,
└───────────────┬───────────────┘  │           LaunchReader,     │  Windows-only
                │                  │           process/name enum │
                │                  └────────┬───────────────┘
                │ depends on                │ depends on
┌───────────────▼───────────────────────────▼───────────────┐
│  core/      LogEntry, parse_line, LEVEL_RANK, query, settings,│  pure Python, NO Qt
│             tabstate, tabtitle, core/dbwin.py, core/winevent.py│
└──────────────────────────────────────────────────────────┘
```

**Dependency direction is strictly one-way: `ui` → `{adb, winlog}` → `core`.** A
lower layer never imports a higher one, and `adb`/`winlog` never import each other
— they're peers, both data sources, both consumed only by `ui`. This is the rule
that keeps the system from collapsing into a tangle: `core` knows nothing about
threads or widgets, so it can be tested in isolation; `adb` and `winlog` know
nothing about widgets, so streaming logic can be reasoned about without the UI.

`winlog/` exists as its own package (not folded into `adb/`) because it's a
different kind of data source — no subprocess, no adb protocol, instead direct
Win32 APIs (`ctypes` for the DBWIN buffer, `pywin32` for Event Log subscription and
process enumeration) — and because keeping it Windows-only-but-isolated means
`core`/`adb`/`ui` stay importable (if not fully functional) on any platform.
`winlog` is imported lazily and every entry point is guarded by that module's own
`is_supported()`, so a non-Windows checkout never touches `ctypes`/`pywin32` at
import time.

### `core/` — pure domain logic

No file under `core/` imports Qt. `models.py` and `parser.py` are the oldest and
most fundamental: `LogEntry` is a frozen, slotted dataclass — immutable so it can
be passed between threads without sharing mutable state — and `parse_line` is a
pure function, string in, `LogEntry` out. That purity is why `tests/test_parser.py`
covers it exhaustively with zero setup, and it's the template the rest of `core/`
follows.

`core/` has grown well past parsing as features landed; roughly, it holds:

- **Domain logic that's genuinely OS/Qt-free**: `query.py` (the query-bar
  grammar), `settings.py` (load/save as plain JSON), `presets.py`, `highlight_rules.py`,
  `history.py`, `devices.py` (adb device-list parsing), and similar single-purpose
  modules — one file per concern, each with its own test file.
- **The pure half of a Windows feature**: `core/dbwin.py` (DBWIN buffer layout →
  `LogEntry`) and `core/winevent.py` (Event Log XML → `LogEntry`) contain the
  *parsing*, deliberately split from `winlog/`'s `ctypes`/`pywin32` plumbing. This
  is the `core` rule paying for itself twice: the Windows-specific struct/XML
  handling is isolated to where it must live, but the mapping logic that's most
  likely to have a bug is testable on Linux CI with fixture bytes/XML, no Windows
  machine required.
- **Tab persistence**: `core/tabstate.py` (what a saved tab looks like — file
  path or serial, query, timestamp — validated so a hand-edited or truncated
  settings file drops the bad entry instead of crashing) and `core/tabtitle.py`
  (composing a tab's label: state marker + name + count, with elision rules) are
  both pure so the persistence format and the label logic are each independently
  unit-tested.

See `CLAUDE.md`'s "Where things live" table for the exhaustive file list — it's
kept current per-change and isn't duplicated here.

### `adb/` and `winlog/` — the reader contract

Every log source in zLog — `AdbReader`, `DebugOutputReader` (DBWIN),
`EventLogReader`, `LaunchReader` (a launched app's stdout/stderr + debug output),
and `FileFollower` (`ui/file_follower.py`, tail -f) — honors the same contract:

- **It's a `QThread`.** Its `run()` method does the actual I/O (subprocess pipe,
  `ctypes` buffer read, `EvtSubscribe` callback, file poll) off the main thread.
- **It parses to `LogEntry` before ever leaving the thread.** `AdbReader` uses
  `core.parser.parse_line`; the Windows readers use `core.dbwin`/`core.winevent`;
  `FileFollower` reuses the logcat parser or falls back to raw text depending on
  the file's format.
- **It communicates with the UI only through signals** — `batch_ready(list[LogEntry])`,
  `error(str)`, and (where relevant) `stream_ended()`. Qt queues these across the
  thread boundary and delivers them to slots on the main thread. **No reader ever
  touches a widget from `run()`.**
- **It batches.** Emitting one signal per line would flood the event loop under a
  busy source. Each reader accumulates a batch and emits once, repeats — the main
  lever for the "stay responsive" goal, tuned per-source since an adb dump and a
  chatty debug stream arrive at different rates.

A new source (the next candidate, per `docs/ROADMAP.md`, would be another
structured Windows or remote source) means writing one more class that honors this
contract — nothing else in `ui/` needs to change to accommodate it, which is the
whole point of stating the contract explicitly instead of leaving it implicit in
`AdbReader`'s code.

### `ui/` — presentation

The UI is built on Qt's model/view framework, which is the key to handling huge
logs:

- **`LogTableModel`** holds the full list of `LogEntry` and exposes it through
  `QAbstractTableModel`. The view asks for `data()` only for the rows currently
  visible — *virtualization*. A million-line log costs a million small objects in a
  list, but rendering only ever touches the rows on screen.

- **`LogFilterProxy`** sits between model and view. `filterAcceptsRow` decides
  visibility from min level, a `tag+message` substring/regex, a tag-contains gate, a
  package PID set, an exclude matcher, and a time-of-day range. Because filtering is
  a view concern, the master list is never mutated — clearing a filter instantly
  reveals everything again.

- **`LogItemDelegate`** (`ui/log_delegate.py`) paints one dense line per visible row
  (no grid): a colored level chip and monospace `time  pid-tid  tag  [proc]  ▮level
  message`, text tinted per level, columns auto-hidden when a source never
  populates them. It runs only for on-screen rows, so the view stays virtualized.
  `ui/log_header_bar.py` paints a thin label strip above the table that reads the
  delegate's own column-width math directly, so the two can never drift apart.

- **`core/query.py`** parses the single query bar (`level: tag: package: pid: proc:
  -exclude /regex/ since: until: text`) into filter gates; `MainWindow._apply_query`
  drives the proxy from it. Pure and unit-tested.

- **`DeviceController`** (`ui/device_controller.py`) holds the device list, the
  remembered serial, and the package/PID filter state — but no widgets. Selection
  preference, filter apply/clear, and live PID tracking live here, so they're
  unit-testable without a `MainWindow`.

- **`CaptureController`** (`ui/capture_controller.py`) is the seam between "a
  reader" and "the window": `attach(session, reader, ...)` wires a reader's signals
  to the window's callbacks and records it against a `LogSession`; `detach` tears
  every reader for that session back down. Before this existed, each of the (now
  five) start paths hand-rolled the same four steps, and it was easy to forget the
  `stream_ended` connection on a new one. A session's *extra* readers — the merged
  multi-device view's other streams, or the DBWIN capture that rides alongside a
  launched app — live in `extra_readers`, so `detach` can never miss one.
  Deliberately widget-free, like `DeviceController`.

- **Open tabs** (`ui/log_session.py`'s `LogSession` holding one tab's model/proxy/
  reader/query state, plus `core/tabstate.py` and `core/tabtitle.py`) let several
  captures run concurrently and survive a restart: `core.tabstate.tabs_to_json` /
  `tabs_from_json` serialize what's open (capped, validated) into settings, and
  `MainWindow` re-opens each on the next launch.

- **`MainWindow`** is the wiring layer: it owns the model, proxy, controllers, and
  widgets, and connects signals to slots. Construction is split out to
  `ui/build.py` (`build_widgets`/`build_layout`) and `ui/menus.py` (`build_menus`)
  so `MainWindow` itself holds wiring and thin slots, not widget construction.

## End-to-end data flow

```
adb logcat ──> AdbReader.run() ───────────┐
DBWIN buffer ──> DebugOutputReader.run() ──┤
Event Log ──> EventLogReader.run() ────────┤  [worker threads]
launched app ──> LaunchReader.run() ───────┤   parse to LogEntry, batch, emit
followed file ──> FileFollower.run() ──────┘   batch_ready(entries) / error(msg)
                            │  (Qt queues each across its thread boundary)
                            ▼
              CaptureController routes the signal to the owning session's slot
                            │                                    [main thread]
              MainWindow.on_batch()  →  session.model.append_entries(entries)
                            ▼
              LogTableModel  ──>  LogFilterProxy  ──>  view + LogItemDelegate
                                   (level+tag+text                (paints visible
                                    +package+exclude+time)         lines, header
                                                                    strip in sync)
```

Every source converges on the same model/proxy/delegate stack — a reader's job
ends at `batch_ready`; everything downstream of that is source-agnostic.

## Why these choices over the alternatives

- **Qt model/view instead of appending widgets per line.** Per-row widgets don't
  scale; the model/view split is purpose-built for large, scrolling datasets.
- **`QThread` + signals instead of polling or `QTimer.readLine`.** A blocking read
  loop (or Win32 wait) on a dedicated thread is simple and robust; signals give
  thread-safe handoff for free — and the same pattern covers five very different
  I/O mechanisms without a shared base class (see the open question this raises,
  below).
- **A separate Qt-free `core` instead of one flat module.** It's what makes the
  logic testable and the codebase approachable as it has grown past parsing into
  settings, presets, tab state, and two Windows-format parsers.
- **`winlog/` as a peer of `adb/`, not folded into it.** They share the reader
  *contract* but not a base class — see `CLAUDE.md`'s note on this; introducing an
  ABC purely to make the package layout tidier would be solving a documentation
  problem with production code.

## Extension points

The layering makes new work additive. For the prioritized, current picture of
what's actually next, see `docs/ROADMAP.md` — the table below is about *where*
a category of change goes, not a commitment to build it:

| Feature category | Where it goes | Notes |
|---|---|---|
| A new log source | a reader class in `adb/` or `winlog/` (or a new peer package if it's neither adb- nor Win32-shaped) honoring the reader contract above | nothing in `ui/` changes to accommodate it beyond wiring `Start` to construct it |
| A new filter gate | extend `LogFilterProxy` + `core/query.py`'s grammar | keep the plain-substring fast path fast |
| A new export format | a serializer in `core/`, driven off the proxy's visible rows | reuses the existing "gather rows → pick a path → write" shape |
| A new dialog/menu action | its own `ui/` module; `MainWindow` wires it up and holds only a thin slot | see `CLAUDE.md`'s rule on keeping `main_window.py` from regrowing |
| Theming | a token on `ui/theme.py`'s `Theme` | never hard-code a hex value in a widget |

When adding any of these, keep the dependency arrows pointing one way and keep all
background work behind signals. If a change seems to require `core` importing Qt or
a worker touching a widget, that's the signal the design is being bent — stop and
reconsider the placement.

## Planning changes

zLog is plan-first: before implementing a feature or notable change, capture it as a
plan in `docs/plans/` (one file per purpose; split large efforts into several). The
plan names the files and layers it touches and shows how it respects the rules
above, and it is approved before any code is written. See `docs/plans/README.md` for
the convention and `docs/plans/TEMPLATE.md` for the structure. The `add-zlog-feature`
and `review-zlog-ui` skills drive this workflow.
