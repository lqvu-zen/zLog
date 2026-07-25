# Plan: Pick a Windows app to focus, and launch one from zLog

- **Status:** Done  <!-- Draft | Approved | In progress | Done | Abandoned -->
- **Owner:** unassigned
- **Created:** 2026-07-24
- **Related:** [windows-debug-output.md](windows-debug-output.md), [package-filter.md](package-filter.md), [device-picker.md](device-picker.md)

## Goal

Focus the Windows debug capture on one app the way the Android side focuses on a
device/package: pick the target from a **process picker** (name + PID) instead of
typing a filter — and, for an app that isn't running yet, **launch its .exe from
zLog** and capture it from its very first line (both its console output and its
`OutputDebugString` tracing).

## Scope

- **In:** (a) a **process picker** in the header when a debug-output tab is
  active: lists all running processes (name + PID, refreshable), selecting one
  applies the existing `proc:`/`pid:` filter — mirroring the Android package
  filter. (b) **File → Launch App…**: choose an .exe (+ optional arguments/working
  dir), zLog starts it, auto-focuses on its PID, and captures **both** its
  stdout/stderr pipes and its DBWIN debug output into one tab.
- **Out (non-goals):** attaching a real debugger, injecting into a running
  process, ETW tracing, elevation/UAC handling for launching as admin, and
  restarting/relaunching on exit. Live file-follow stays its own backlog item.

## Design

Two independent pieces that share the same "focus" concept. Focus is expressed
through the **existing query tokens** (`proc:<name>` / `pid:<n>`) — no new proxy
gate — so everything downstream (chips, presets, export, histogram) works as-is.

**Process enumeration** is Windows-only, so it splits like the DBWIN work did:
the pure shaping/sorting/matching lives in `core/`, the Win32 call in `winlog/`.

**Launching** uses `subprocess.Popen` (cross-platform), reading stdout+stderr on a
thread and emitting the same `batch_ready` signal — so a launched **console** app
works on any OS, while its DBWIN tracing is picked up by the existing capture on
Windows. Two readers can feed one tab (the model just appends), matching how the
merged multi-device view already fans several readers into one model.

| File | Layer | Change |
|---|---|---|
| `src/zlog/core/procinfo.py` (new) | core | Pure, OS-free: `ProcessInfo(pid, name)`; `sort_processes(procs)` (name-insensitive, pid tiebreak); `filter_processes(procs, needle)` for the picker's type-to-search; `focus_query(existing_query, name=None, pid=None) -> str` — rewrite the query's `proc:`/`pid:` token(s) to the chosen target, reusing `core.query` span logic so other tokens survive. Unit-tested. |
| `src/zlog/winlog/processes.py` (new) | winlog | `list_processes() -> list[ProcessInfo]` via ctypes Toolhelp (`CreateToolhelp32Snapshot`/`Process32First`/`Next`), guarded + lazily imported; returns `[]` off Windows. Complements the existing per-pid `procnames.py`. |
| `src/zlog/winlog/launcher.py` (new) | winlog (cross-platform) | `LaunchReader(QThread)`: `Popen(argv, cwd=…, stdout=PIPE, stderr=STDOUT, text, errors="replace", bufsize=1)`, reads lines, wraps each as a `LogEntry` (tag = exe base name, pid = the child's real pid, `source="stdout"`, level via `core.dbwin.infer_level`), batching with the shared `should_flush`. Signals `batch_ready` / `error` / `stream_ended` + exposes `pid` so the window can focus on it. `stop()` terminates the child. |
| `src/zlog/ui/process_dialog.py` (new) | ui | `ProcessPickerDialog`: searchable list of `list_processes()` (name + PID), Refresh, OK → returns the chosen `ProcessInfo`. Empty/na state off Windows. |
| `src/zlog/ui/launch_dialog.py` (new) | ui | `LaunchDialog`: exe path (Browse…), arguments, working directory; returns argv + cwd. Remembers the last few launches in settings (reuse `push_history`). |
| `src/zlog/ui/main_window.py` | ui | **Picker:** a `focus_btn` ("Focus App…") next to the package box, enabled when the active tab is a debug/launch capture; opens `ProcessPickerDialog`, then `_set_query_text(focus_query(...))`. **Launch:** `File → Launch App…` → `LaunchDialog` → open/reuse a tab, start `LaunchReader` **and** (on Windows) the existing `DebugOutputReader`, focus the query on the child's pid, label the tab `● <exe name>`. Both readers land in the same session; `stop()` stops both (extend the existing `_merged_readers` list rather than adding new state). |
| `docs/GUIDE.md` | — | Extend the Windows section: pick a running app with **Focus App…**, or start one with **File → Launch App…** (captures console + debug output from the first line). |
| `tests/test_procinfo.py`, `tests/test_launcher.py` (new) | — | Pure sorting/filtering/`focus_query` cases; a `LaunchReader` end-to-end using a tiny `python -c "print(...)"` child (cross-platform, no Windows needed) asserting entries arrive and `stop()` terminates. |

## Architecture touch points

- **Threading:** `LaunchReader` is another `QThread` emitting `batch_ready` —
  never touching widgets. A launched app therefore streams exactly like adb.
  Two readers per tab is already the merged-view pattern; both must be stopped.
- **Model/proxy:** no new gate or column. Focus = rewriting `proc:`/`pid:` in the
  query, so chips/presets/export keep working. `source` distinguishes
  `"dbwin"` vs `"stdout"` rows if we ever want to tint them.
- **Dependency direction:** `ui → winlog → core`; `core/procinfo.py` stays
  OS-free/Qt-free so it tests on Linux. `launcher.py` is cross-platform (stdlib
  `subprocess`), only `processes.py` is Windows-gated.

## Risks & regressions to check

- **PID reuse / exit:** the picked process may die; focusing by `pid:` then goes
  quiet. Offer name-based focus (`proc:`) as the default and pid as the precise
  option — and say so in the dialog.
- **Launched GUI apps have no console output** — that's expected; their DBWIN
  tracing still arrives. Don't present an empty stdout as an error.
- **Child cleanup:** `stop()`, closing the tab, and quitting the app must all
  terminate the child (no orphans); verify the reader thread exits (pipe read is
  blocking — closing the pipe/terminating unblocks it).
- **Two readers, one tab:** stopping must stop both; the tab label and
  Start/Stop/pause enablement must stay consistent (reuse the existing paths).
- **Quoting/paths:** spaces in exe path/args (build argv as a list, never a
  string); a bad path must report cleanly, not raise.
- **Encoding:** child output decoded with `errors="replace"` (same as `AdbReader`).
- **Off-Windows:** the picker reports "Windows only" and lists nothing; launching
  still works (console capture), so guard only the enumeration.
- **Existing flows:** adb device/package filtering, tabs, and the DBWIN capture
  must be unaffected when the new controls are hidden/disabled.

## Verification

- [ ] `uv run pytest` (new `test_procinfo.py` / `test_launcher.py`; suites green on Linux)
- [ ] `uv run ruff check .` and `uv run ruff format --check .`
- [ ] Smoke/screenshot via `run-zlog` of the picker + launch dialogs
- [ ] Manual on Windows: pick a running app → only its lines remain; launch a
      console .exe → its stdout appears from the first line; launch an app that
      calls `OutputDebugString` → both streams land in the tab; Stop kills the child.

## Open questions

- **Focus default:** `proc:<name>` (survives restarts) vs `pid:<n>` (exact, but
  dies with the process). Leaning name by default, with a "this PID only" checkbox.
- **Picker placement:** reuse the package box/Focus button in the header, or make
  it a toolbar action only? Leaning a button beside the package box, shown for
  Windows-capture tabs.
- **Auto-start capture:** should **Launch App…** implicitly turn on DBWIN capture
  if it isn't running? Leaning yes (that's the point of launching from zLog).
- **Relaunch:** offer a "restart app" button once launched? Deferred unless wanted.
