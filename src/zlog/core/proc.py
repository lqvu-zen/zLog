"""Detect process-start lines in logcat — pure, no Qt, so it's unit-testable.

ActivityManager announces a new process when an app (re)starts. Two historical
shapes are handled:

  newer:  "Start proc 12345:com.example.app/u0a123 for activity ..."
  older:  "Start proc com.example.app for activity ...: pid=12345 uid=..."
"""

from __future__ import annotations

import re

_MODERN = re.compile(r"Start proc (?P<pid>\d+):(?P<package>[\w.]+)")
_LEGACY = re.compile(r"Start proc (?P<package>[\w.]+) for .*\bpid=(?P<pid>\d+)")


def parse_proc_start(message: str) -> tuple[str, str] | None:
    """Return ``(pid, package)`` for a process-start line, else ``None``."""
    m = _MODERN.search(message)
    if m:
        return m.group("pid"), m.group("package")
    m = _LEGACY.search(message)
    if m:
        return m.group("pid"), m.group("package")
    return None
