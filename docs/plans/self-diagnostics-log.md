# Plan: Self-diagnostics log (zLog logs its own behavior)

- **Status:** Done  <!-- Draft | Approved | In progress | Done | Abandoned -->
- **Owner:** unassigned
- **Created:** 2026-07-15
- **Related:** [perf-start-freeze.md](perf-start-freeze.md), [wrap-messages.md](wrap-messages.md)

## Goal

When zLog itself misbehaves (a freeze, an adb failure, a crash), there is a
persistent rotating log file on disk describing what happened — so bugs can be
diagnosed from the file instead of guessed at, including in the frozen `.exe`
build where there is no console.

## Scope

- **In:** a stdlib-`logging` setup writing to a rotating `zlog.log`; a startup
  version/environment banner; adb/reader errors logged with tracebacks; a global
  `sys.excepthook` + Qt message handler so uncaught errors are captured; a
  **Help → Open Log Folder** action to find the file.
- **Out (non-goals):** a Settings log-level selector (env var only for now);
  DEBUG tracing of hot paths (batching/scroll/filter); any change to how the
  *logcat* data the app displays is handled. This is purely zLog's own diagnostics.

## Design

| File | Layer | Change |
|---|---|---|
| `src/zlog/core/applog.py` (new) | core | `configure(log_dir: str, level: str \| None) -> Path` sets up a `logging.getLogger("zlog")` with a `RotatingFileHandler` (3 × 1 MB, UTF-8) at `<log_dir>/zlog.log`; idempotent (won't double-add handlers). `log_path(log_dir)` helper. Reads `ZLOG_LOG_LEVEL` env (default `INFO`) when `level` is None. Pure stdlib — no Qt. |
| `src/zlog/app.py` | ui/app | Call `applog.configure(...)` first thing in `main()` (before `MainWindow`), passing the same `AppConfigLocation` dir the settings use. Install a `sys.excepthook` that logs the traceback (then chains to the default hook) and a `qInstallMessageHandler` that routes Qt warnings to the logger. Log a start banner: zLog `__version__`, Python, PySide6/Qt versions, platform. |
| `src/zlog/adb/reader.py` | adb | In the two `error.emit(...)` paths, also `logger.exception(...)` / `logger.error(...)` so reader failures land in the file with a traceback. (Keep emitting the signal — the status bar behavior is unchanged.) |
| `src/zlog/ui/main_window.py` | ui | Log key lifecycle events at INFO: stream start/stop with the resolved `adb` argv, device selected, clear/clear-device, settings load/save failures (the existing `except` around `save_settings`). Add a **Help** menu (or an entry on the existing menu) → **Open Log Folder** using `QDesktopServices.openUrl` on the log dir. |
| `tests/test_applog.py` (new) | — | Unit-test `configure()` in a `tmp_path`: file is created, a logged line lands in it, level honors the env var, and calling `configure()` twice does not duplicate handlers. All Qt-free. |

## Architecture touch points

- **Threading:** `AdbReader` runs in a `QThread`. Python's `logging` is
  thread-safe, so the reader can call the logger directly; no new signal needed.
  The UI still learns of errors via the existing `error` signal — logging is
  additive.
- **Model/proxy:** unchanged. No new column or filter.
- **Dependency direction:** `core/applog.py` imports only stdlib (`logging`,
  `logging.handlers`, `os`) — respects Qt-free `core`. The excepthook, Qt message
  handler, and menu wiring live in `app.py` / `ui`, i.e. `ui → adb → core` holds.

## Risks & regressions to check

- Logging must never crash the app: `configure()` wraps handler setup so a
  read-only/again-unwritable log dir degrades to no file handler, not an
  exception at startup.
- No PII surprises: log the adb argv and device serial (already visible in the
  UI), but not full logcat message bodies — those can be verbose and sensitive.
- The `sys.excepthook` must chain to the previous hook so behavior (and pytest)
  isn't swallowed; install it only in `main()`, never at import time.
- Rotation cap (3 × 1 MB) keeps disk bounded; verify old files roll over.
- Start/stop streaming, clear, and settings save still behave exactly as before.

## Verification

- [ ] `uv run pytest` (incl. new `test_applog.py`)
- [ ] `uv run ruff check .` and `uv run ruff format --check .`
- [ ] Manual: launch, start a stream, trigger an adb error (unplug device),
      confirm `zlog.log` shows the banner + the error traceback; Help → Open Log
      Folder opens the right directory.

## Open questions

- Menu placement: a new top-level **Help** menu, or hang **Open Log Folder** off
  the existing **File**/**View** menu? (Leaning H