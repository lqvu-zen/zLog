# Plan: Fix AdbReader crash on non-cp1252 logcat bytes

- **Status:** In progress
- **Owner:** unassigned
- **Created:** 2026-07-08
- **Related:** none

## Goal

After this ships, `adb logcat` output containing non-ASCII bytes (emoji,
non-English app messages, native-crash binary garbage) no longer crashes the
streaming thread — the app keeps reading instead of silently going dead.

## Findings
User hit this in real use (traceback below), not a review — filing under the
same Findings/Design shape as this repo's UI-review plans since it's the
project's plan-first convention for any fix.

### High
> Hurts usability or looks broken — the log stream silently stops.

#### H1. `AdbReader.run()` crashes on the first non-cp1252 byte from logcat
- **Location:** `src/zlog/adb/reader.py:43-71` (`run`'s `Popen` call and read loop).
- **What & why:** `subprocess.Popen(..., text=True, ...)` is given no
  `encoding`, so Python decodes `adb`'s stdout using the platform's default
  text encoding — on this Windows box, `cp1252`. Logcat output is UTF-8 (app
  messages routinely contain non-ASCII text, emoji, or raw bytes from a native
  crash), so the first byte outside cp1252's range raises `UnicodeDecodeError`
  from inside the `for raw in self._proc.stdout:` loop. That's uncaught, so
  `QThread.run()` exits via the exception — Qt logs "Error calling Python
  override of QThread::run()" to the console and the thread dies. Nothing
  reaches the `error` signal, so the UI shows no message at all: the status bar
  just stops climbing and the user has no idea streaming silently died attack
  (exactly the "silent or frozen state" the project's own UI heuristics flag as
  a bug). Two reported tracebacks (positions 3086, 2799) confirm it's not a
  one-off — any sufficiently long real capture will hit this.
- **Recommendation:** decode as UTF-8 with `errors="replace"`, matching the
  precedent already used for file loads in `main_window.py:785`
  (`open(path, encoding="utf-8", errors="replace")`). Also wrap the read loop
  so any *other* unexpected read/decode failure still reaches the `error`
  signal instead of dying silently, consistent with this class's existing
  error-reporting contract (used today for a missing `adb` binary).
- **Screenshot:** n/a — not a visual finding.

### What already works well
- The `error` signal / `FileNotFoundError` handling for a missing `adb` binary
  is a good existing pattern — this fix extends the same contract to the read
  loop rather than inventing a new one.

### Deferred
- None.

## Scope

- **In:** `AdbReader.run()` — correct the stdout decode, and route any
  in-loop exception through `self.error` instead of letting it kill the thread.
- **Out (non-goals):** no change to the parser, batching, start/stop control
  flow, or any other reader behavior.

## Design

| File | Layer | Change |
|---|---|---|
| `src/zlog/adb/reader.py` | adb | `Popen(..., encoding="utf-8", errors="replace", ...)` instead of `text=True` (equivalent for line-iteration, but pins the codec instead of inheriting the platform default). |
| `src/zlog/adb/reader.py` | adb | Wrap the `for raw in self._proc.stdout:` loop body in `try/except Exception`, emit `self.error.emit(f"Log reading stopped: {exc}")` and `break` on failure, so a future unexpected decode/read error surfaces to the UI instead of silently killing the thread. |

## Architecture touch points

- **Threading:** unchanged — still emits `batch_ready`/`error` from the
  background thread, delivered to the main thread by Qt as before. No new
  cross-thread state.
- **Model/proxy:** none.
- **Dependency direction:** unaffected — `adb/reader.py` stays below `ui/`.

## Risks & regressions to check

- `errors="replace"` swaps undecodable bytes for U+FFFD rather than dropping
  the line — confirm a line with a replaced character still parses (an
  unparsed/garbled tag beats losing the line, per `parser.py`'s existing
  "never silently drop a line" contract).
- The new `except Exception` must not swallow the intentional `stop()` path —
  `stop()` sets `_running = False` then calls `proc.terminate()`, which ends
  the stdout iteration naturally (EOF) rather than raising, so it shouldn't
  trip the new handler; verify a normal Stop still ends cleanly with no
  spurious error message.
- Any batch already accumulated before a mid-stream failure should still be
  flushed via `batch_ready` before reporting the error, so partial progress
  isn't lost.

## Verification

- [ ] `uv run pytest`
- [ ] `uv run ruff check .` and `uv run ruff format --check .`
- [ ] Add a regression test that feeds `AdbReader` a raw byte sequence outside
      cp1252 (reproducing the reported crash) and confirms it's decoded via
      `errors="replace"` instead of raising.
- [ ] Confirm the normal Stop path (EOF from `terminate()`) still ends cleanly
      with no spurious error message from the new exception handler.
