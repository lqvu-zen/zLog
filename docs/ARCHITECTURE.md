# zLog Architecture

This document explains *how zLog is put together and why*. `CLAUDE.md` is the quick
reference; this is the reasoning behind it. Read it before making a structural
change (new layer, new threading path, new data source).

## Goals that shape the design

1. **Stay responsive under heavy log volume.** `adb logcat` can emit thousands of
   lines per second. The UI must never stutter or freeze.
2. **Be testable without a display.** Core logic (parsing, filtering rules) should
   run under CI/pytest with no Qt platform and no device attached.
3. **Be easy to extend.** Adding a device picker, a package filter, or save/load
   should slot into a clear place, not require touching everything.

Every decision below serves one of these.

## The three layers

```
┌──────────────────────────────────────────────┐
│  ui/        QApplication, MainWindow,          │  Qt widgets
│             LogTableModel, LogFilterProxy,     │
│             LogItemDelegate, DeviceController   │
└───────────────┬───────────────────────────────┘
                │ depends on
┌───────────────▼───────────────────────────────┐
│  adb/       AdbReader (QThread)                 │  Qt threading + subprocess
└───────────────┬───────────────────────────────┘
                │ depends on
┌───────────────▼───────────────────────────────┐
│  core/      LogEntry, parse_line, LEVEL_RANK    │  pure Python, NO Qt
└────────────────────────────────────────────────┘
```

**Dependency direction is strictly one-way: `ui` → `adb` → `core`.** A lower layer
never imports a higher one. This is the rule that keeps the system from collapsing
into a tangle: `core` knows nothing about threads or widgets, so it can be tested
in isolation; `adb` knows nothing about widgets, so the streaming logic can be
reasoned about without the UI.

### `core/` — pure domain logic

`models.py` and `parser.py` contain no Qt imports at all. `LogEntry` is a frozen,
slotted dataclass — immutable so it can be passed between threads without sharing
mutable state, and cheap to allocate in bulk. `parse_line` is a pure function:
string in, `LogEntry` out, no side effects. That purity is why `tests/test_parser.py`
can cover it exhaustively with zero setup.

**Anything that doesn't need Qt belongs here.** A future PID→process-name map, a
log-format detector, or a saved-session serializer are all `core/` citizens.

### `adb/` — the data source

`AdbReader` is the one place that knows how to get logs. It subclasses `QThread`
and, in `run()` (which executes on the worker thread), spawns
`adb logcat -v threadtime` and reads its stdout line by line, parsing each via
`core.parse_line`.

Two design points matter here:

- **It communicates with the UI only through signals.** Qt widgets are not
  thread-safe; writing to a widget from the worker thread will eventually crash or
  corrupt the display. So the reader emits `batch_ready(list[LogEntry])` and
  `error(str)`. Qt queues these across the thread boundary and delivers them to
  slots running on the main thread. **No widget is ever touched from `run()`.**

- **It batches.** Emitting one signal per line would flood the event loop under a
  busy log. The reader accumulates `_BATCH_SIZE` (50) entries, emits once, repeats.
  This is the main lever for the "stay responsive" goal.

### `ui/` — presentation

The UI is built on Qt's model/view framework, which is the key to handling huge
logs:

- **`LogTableModel`** holds the full list of `LogEntry` and exposes it through
  `QAbstractTableModel`. The view asks for `data()` only for the rows currently
  visible — *virtualization*. A million-line log costs a million small objects in a
  list, but rendering only ever touches the ~50 rows on screen.

- **`LogFilterProxy`** sits between model and view. `filterAcceptsRow` decides
  visibility from min level, a `tag+message` substring/regex, a tag-contains gate, a
  package PID set, and an exclude matcher. Because filtering is a view concern, the
  master list is never mutated — clearing a filter instantly reveals everything again.

- **`LogItemDelegate`** (`ui/log_delegate.py`) paints one dense line per visible row
  (no grid): a colored level chip and monospace `time  pid-tid  tag  ▮level  message`,
  text tinted per level. It runs only for on-screen rows, so the view stays virtualized.

- **`core/query.py`** parses the single query bar (`level: tag: package: -exclude
  /regex/ text`) into a `QuerySpec`; `MainWindow._apply_query` drives the proxy gates
  from it. Pure and unit-tested.

- **`DeviceController`** (`ui/device_controller.py`) holds the device list, the
  remembered serial, and the package/PID filter state — but no widgets. Selection
  preference, filter apply/clear, and live PID tracking live here, so they're
  unit-testable without a `MainWindow`. The window drives its widgets and the proxy
  from the controller's state.

- **`MainWindow`** is the wiring layer. It owns the reader, model, proxy, controller,
  and widgets, and connects signals to slots. It contains as little logic as possible;
  anything substantial should live in a lower layer it calls into.

## End-to-end data flow

```
device ──adb logcat──> AdbReader.run()  [worker thread]
                            │ parse_line per line, accumulate 50
                            │ emit batch_ready(entries)
                            ▼  (Qt queues across thread boundary)
              MainWindow.on_batch()      [main thread]
                            │ model.append_entries(entries)
                            ▼
              LogTableModel  ──>  LogFilterProxy  ──>  view + LogItemDelegate
                                   (level+tag+text     (paints visible lines)
                                    +package+exclude)
```

## Why these choices over the alternatives

- **Qt model/view instead of appending widgets per line.** Per-row widgets don't
  scale; the model/view split is purpose-built for large, scrolling datasets.
- **`QThread` + signals instead of polling or `QTimer.readLine`.** A blocking read
  loop on a dedicated thread is simple and robust; signals give thread-safe handoff
  for free.
- **A separate Qt-free `core` instead of one flat module.** It's what makes the
  logic testable and the codebase approachable as it grows.

## Extension points

The layering makes the planned features additive:

| Feature | Where it goes | Notes |
|---|---|---|
| Device picker | parse `adb devices` in `adb/` (or a new `core` helper); pass serial to `AdbReader(serial=...)` and `adb -s <serial> logcat` | UI adds a combo that recreates the reader |
| Package/PID filter | extend `LogFilterProxy` + a PID→name map in `core/` | no new layer needed |
| Save / load sessions | a serializer in `core/`; load path feeds `model.append_entries` | offline viewing reuses the whole UI |
| Regex search | a mode flag on `LogFilterProxy` | keep the plain substring fast path |
| Theming | a new `ui/theme.py` holding color tokens | migrate `LEVEL_COLOR` into it |

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
