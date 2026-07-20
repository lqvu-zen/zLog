"""Headless tail mode: `zlog --tail` streams filtered logcat to stdout.

Reuses the same command builder, parser, and query gates as the GUI, so a
scripted `zlog --tail --filter 'level:E -Choreographer'` behaves like the query
bar. Qt-free (no QApplication) so it works in plain terminals and pipes.
"""

from __future__ import annotations

import subprocess
import sys
from collections.abc import Callable

from zlog.adb.reader import build_logcat_command
from zlog.core.logfilter import build_predicate
from zlog.core.models import LogEntry
from zlog.core.parser import parse_line
from zlog.core.query import parse_query


def format_entry(entry: LogEntry) -> str:
    """One-line threadtime-style rendering for stdout."""
    return f"{entry.time} {entry.pid}-{entry.tid} {entry.level} {entry.tag}: {entry.message}"


def run_tail(
    serial: str | None,
    filter_text: str,
    adb_path: str,
    buffers: list[str] | None,
    tail: int,
    out=None,
    _spawn: Callable | None = None,
) -> int:
    """Stream matching lines to `out` (default stdout). Returns a process-style
    exit code: 0 normal/interrupted, 2 when adb isn't found.

    `_spawn` is an injection point for tests (defaults to subprocess.Popen).
    """
    out = out if out is not None else sys.stdout
    predicate = build_predicate(parse_query(filter_text or ""))
    cmd = build_logcat_command(adb_path or "adb", serial, buffers, tail)
    spawn = _spawn or (
        lambda: subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )
    )
    try:
        proc = spawn()
    except FileNotFoundError:
        print(f"zlog: could not find '{adb_path or 'adb'}' on PATH.", file=sys.stderr)
        return 2

    try:
        for raw in proc.stdout:
            entry = parse_line(raw.rstrip("\n"))
            if predicate(entry):
                print(format_entry(entry), file=out, flush=True)
    except KeyboardInterrupt:
        pass
    finally:
        if getattr(proc, "terminate", None):
            proc.terminate()
    return 0
