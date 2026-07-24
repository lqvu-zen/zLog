# Plan: Capture Windows app debug output (OutputDebugString) as a source

- **Status:** Draft  <!-- Draft | Approved | In progress | Done | Abandoned -->
- **Owner:** unassigned
- **Created:** 2026-07-24
- **Related:** [merged-multidevice.md](merged-multidevice.md), [device-tabs.md](device-tabs.md), [open-in-new-tab.md](open-in-new-tab.md)

## Goal

Use zLog to watch the live debug output of any running Windows app — the
`OutputDebugString` stream that C/C++, .NET (`Debug`/`Trace`), Qt, Electron, and
most frameworks emit — tagged by process, so you can filter to the app you're
debugging with the existing `pid:` / `proc:` tokens.

## Scope

- **In:** a new *source* alongside adb devices — "Windows Debug Output". Start it
  in a tab and it streams every `OutputDebugString` line the system publishes to
  the shared `DBWIN` buffer (this is what Sysinternals DebugView reads), each row
  stamped with the emitting **PID** and resolved **process name**. Reuses the whole
  view: query bar, level/tag/pid filters, presets, histogram, export. Session-local
  capture (no admin).
- **Out (non-goals):** launch-and-capture of a console app's stdout/stderr, live
  file-follow (`tail -f`), ETW provider tracing, and the Windows **Event Log**
  channels — each is a separate source and its own plan (see [backlog.md](backlog.md)).
  Global/session-0 (services) capture beyond a best-effort note. Non-Windows: the
  source simply isn't offered.

## How DBWIN capture works (background)

Windows routes `OutputDebugString` to a single system-wide 4 KB shared section
named `DBWIN_BUFFER`, coordinated by two events, `DBWIN_BUFFER_READY` and
`DBWIN_DATA_READY`. A capturer owns these objects and loops: signal
`DBWIN_BUFFER_READY`, wait on `DBWIN_DATA_READY`; when signaled, the buffer holds a
4-byte process id (DWORD) followed by a NUL-terminated ANSI string. Read it, emit
`(pid, message)`, repeat. Only one capturer can own the buffer at a time.

## Design

Debug lines map onto the existing `LogEntry(time, pid, tid, level, tag, message,
source)`, so nothing in the model/proxy/delegate/query changes:
- **PID** (from the buffer) → `pid`; there is no TID → `tid = ""`.
- **Process name** (resolved from the PID) → `tag`, so `proc:`/`tag:`, mute-tag,
  and Tag Summary all work; `source` stamps `"dbwin"` so a merged tab can separate
  it from adb rows.
- **Message** → `message`; the app supplies no severity, so `level` defaults to `I`
  with an optional heuristic (`error`/`fail`/`exception` → `E`, `warn` → `W`).
- **Arrival time** → `time`, formatted `"MM-DD HH:MM:SS.mmm"` to match logcat.

| File | Layer | Change |
|---|---|---|
| `src/zlog/core/dbwin.py` (new) | core | Pure, **OS-free** (no ctypes, no Qt): `parse_dbwin_record(buf: bytes) -> tuple[int, str]` (split the DWORD pid + ANSI message from the raw buffer bytes); `infer_level(message) -> str`; `build_entry(pid, name, message, now) -> LogEntry`. Unit-tested with byte fixtures — runs on Linux/CI. |
| `src/zlog/winlog/__init__.py`, `src/zlog/winlog/dbwin_reader.py` (new) | winlog (peer of `adb/`) | `DebugOutputReader(QThread)` with the **same signals** as `AdbReader`: `batch_ready(list[LogEntry])`, `error(str)`. Sets up the `DBWIN_BUFFER` section + the two events (stdlib `mmap` with `tagname=` for the section; `ctypes.windll.kernel32` for `CreateEvent`/`SetEvent`/`WaitForSingleObject`) — **no new dependency**. Loop parses via `core.dbwin`, resolves PID→name (cached), batches with the existing `should_flush` cadence. `stop()` sets a flag and signals `DBWIN_DATA_READY` to wake the wait, then releases the objects. All Windows API access is lazily imported/guarded so import on Linux is safe. |
| `src/zlog/winlog/procnames.py` (new) | winlog | PID → image name via `ctypes` Toolhelp (`CreateToolhelp32Snapshot`) or `QueryFullProcessImageName`, with a small cache (PIDs get reused/exit). Windows-only, guarded. |
| `src/zlog/ui/device_controller.py` / `ui/main_window.py` | ui | Generalize "device" → "source": the source picker adds "Windows Debug Output"; Start routes to `DebugOutputReader`. Each tab/`LogSession` already owns its reader, so a debug-output tab sits beside an Android tab unchanged. Tab label = `● Debug Output` while capturing. A convenience "focus process" action (write `proc:<name>` into the query) is optional polish. |
| `pyproject.toml` | — | No new runtime dependency (ctypes + stdlib `mmap`). If PID→name proves fiddly, `psutil; sys_platform == "win32"` is a fallback — see open questions. |
| `docs/GUIDE.md` | — | A "Windows debug output" section: Start the source, filter to your app with `proc:` / `pid:`, note the DebugView/debugger contention caveat. |
| `tests/test_dbwin.py` (new) | — | `parse_dbwin_record` over fixture buffers (normal, empty message, missing NUL, non-ASCII/mbcs), `infer_level`, `build_entry` mapping. All OS-free. |

## Architecture touch points

- **Threading:** `DebugOutputReader` does all Win32 work off the main thread and
  reaches the UI only via `batch_ready` / `error`, exactly like `AdbReader`.
  Batching reuses `should_flush` so a chatty app can't flood the event loop; the
  existing ring-buffer cap bounds memory.
- **Model/proxy:** none new. Rows are `LogEntry`; every gate (level, tag, pid,
  exclude, source) applies. `proc:<app>` is how you "focus" on a target.
- **Dependency direction:** `ui → winlog → core`, matching `ui → adb → core`.
  `core/dbwin.py` imports neither Qt nor any Windows API (OS-free), so `core/`
  tests stay headless and cross-platform.

## Risks & regressions to check

- **Single-owner buffer:** if DebugView, another zLog, or a debugger already owns
  `DBWIN_BUFFER`, setup fails — detect and report cleanly via `error`, don't hang.
- **Debugger steals output:** a process running under a debugger sends its
  `OutputDebugString` to that debugger, not to `DBWIN`; note in the GUIDE.
- **ANSI decoding:** the buffer is ANSI even for `OutputDebugStringW` (the system
  converts); decode as `mbcs`/`latin-1` with `errors="replace"`, never crash.
- **Admin scope:** session-local capture is non-admin; services/session-0 need
  elevation + `Global\` names — report the limitation, don't silently miss them.
- **Stop wakeup:** `WaitForSingleObject` must be woken on `stop()` (signal
  `DBWIN_DATA_READY`) so the thread exits promptly; verify no hang on quit.
- **PID→name races:** a PID may exit/reuse before resolution; cache best-effort,
  fall back to the raw PID as the tag.
- **Volume:** a very chatty app — confirm batching + ring cap hold (perf smoke).
- **Cross-platform:** all ctypes/mmap/Win32 access guarded; app import + full test
  suite must stay green on Linux/CI (only `core/dbwin.py` is exercised there).

## Verification

- [ ] `uv run pytest` (new `test_dbwin.py`; existing suites green on Linux)
- [ ] `uv run ruff check .` and `uv run ruff format --check .`
- [ ] Smoke/screenshot via `run-zlog` for the source picker entry
- [ ] Manual on Windows: run a small app that calls `OutputDebugString` (or the
      `DebugView` test), Start the source, confirm PID + process name populate and
      `proc:<app>` isolates it; confirm a clean error when DebugView is already
      capturing, and a graceful "Windows only" on Linux.

## Open questions

- **Phasing:** land `core/dbwin.py` + tests first (zero-risk, OS-free), then the
  reader, then the source-selector UI? Leaning yes.
- **PID→name:** pure `ctypes` Toolhelp (zero dependency) vs. adding `psutil`
  (Windows-only, simpler, richer). Leaning ctypes to keep deps at zero.
- **Level heuristic:** infer `E`/`W` from message text, or keep everything `I` and
  let the user filter by substring? Leaning a small, documented heuristic that's
  easy to turn off.
- **Focus UX:** is `proc:`/`pid:` filtering enough, or do we want a running-process
  picker to click your target? Leaning tokens first, picker as later polish.
- **Global capture:** offer an opt-in "capture services (needs admin)" toggle now,
  or defer? Leaning defer to keep v1 non-admin and simple.
