"""Expand a watch-action command template into a safe argv list.

The template is user-authored text like ``notify-send {tag} {message}``. It is
split into argv **before** any log data is substituted in, so untrusted log
content (which can contain ``;``, ``&&``, quotes, anything) only ever lands
inside an already-fixed argv slot — it can never add an argument or be
interpreted by a shell, because we never build a shell string and never pass
``shell=True``.
"""

from __future__ import annotations

import os
import re
import shlex

from zlog.core.models import LogEntry

_PLACEHOLDER_RE = re.compile(r"\{(message|tag|pid|level|time|line)\}")


def _raw_line(entry: LogEntry) -> str:
    return f"{entry.time} {entry.pid}-{entry.tid} {entry.tag} {entry.level} {entry.message}"


def expand_command(template: str, entry: LogEntry) -> list[str]:
    """Parse ``template`` as argv and substitute ``{placeholder}`` values from
    ``entry``. Returns ``[]`` for a blank template. Unknown placeholders (e.g.
    ``{oops}``) are left literal rather than raising, since a typo shouldn't
    crash the watch action."""
    template = (template or "").strip()
    if not template:
        return []
    # posix=False on Windows keeps backslashes in paths (e.g. C:\foo\bar.exe)
    # from being eaten as escape characters, matching launcher.build_argv.
    argv = shlex.split(template, posix=(os.name != "nt"))
    values = {
        "message": entry.message,
        "tag": entry.tag,
        "pid": entry.pid,
        "level": entry.level,
        "time": entry.time,
        "line": _raw_line(entry),
    }
    return [_PLACEHOLDER_RE.sub(lambda m: values[m.group(1)], token) for token in argv]
