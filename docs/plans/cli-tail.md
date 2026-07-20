# Plan: Headless CLI tail mode

- **Status:** Done
- **Owner:** unassigned
- **Created:** 2026-07-20
- **Related:** [package-filter.md](package-filter.md), [exclude-filter.md](exclude-filter.md)

## Goal

Run `zlog --tail --filter '<query>'` from a terminal to stream filtered logcat to
stdout with no GUI, so zLog's query language is usable in scripts and pipes.

## Design

| File | Layer | Change |
|---|---|---|
| `src/zlog/core/logfilter.py` (new) | core | `build_predicate(spec) -> (LogEntry)->bool` mirroring the proxy's headless-supportable gates (min/exact level, tag, pid include/exclude, search + exclude text/regex over tag+message). Qt-free, unit-tested. |
| `src/zlog/cli.py` (new) | ui-adjacent (no Qt) | `format_entry`, `run_tail(serial, filter, adb, buffers, dump, out, _spawn)` reusing `build_logcat_command` + `parse_line` + `build_predicate`; `_spawn` injection for tests. |
| `src/zlog/app.py` | app | `_parse_cli` (argparse) recognizes `--tail/--serial/--filter/--adb/--buffers/--dump`; `main()` routes to `run_tail` when `--tail`, else builds the GUI from leftover args. |
| `tests/test_cli.py` (new) | — | predicate gates, format, filtered streaming via a fake process, missing-adb exit code. |

## Non-goals

- `proc:`/`-proc:` (needs the live PID→name map) and `since:`/`until:` are GUI-only
  and ignored by the CLI predicate (documented in the module).

## Verification

- [x] `uv run pytest tests/test_cli.py`
- [x] `uv run ruff check .` / `format --check`
