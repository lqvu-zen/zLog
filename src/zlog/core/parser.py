"""Parse raw logcat text into LogEntry objects.

Pure functions only — no Qt, no I/O — so this is trivially unit-testable.

We stream with `-v threadtime`, but opened log files may be captured in another
format, so `parse_line` recognizes the common ones (threadtime, time, brief, tag)
and falls back to the raw line for anything else (banners, wrapped output), so
nothing is silently dropped.
"""

from __future__ import annotations

import re

from zlog.core.logformat import CompiledFormat, LogFormat, apply_aliases, compile_formats
from zlog.core.models import LogEntry

# `-v threadtime`:  06-30 12:34:56.789  1234  5678 I SomeTag : the message
_THREADTIME = re.compile(
    r"^(?P<time>\d\d-\d\d \d\d:\d\d:\d\d\.\d+)\s+"
    r"(?P<pid>\d+)\s+(?P<tid>\d+)\s+"
    r"(?P<level>[VDIWEF])\s+"
    r"(?P<tag>.*?):\s?"
    r"(?P<message>.*)$"
)

# `-v time`:  06-30 12:34:56.789 I/SomeTag(  1234): the message
_TIME = re.compile(
    r"^(?P<time>\d\d-\d\d \d\d:\d\d:\d\d\.\d+)\s+"
    r"(?P<level>[VDIWEF])/(?P<tag>.*?)\(\s*(?P<pid>\d+)\):\s?"
    r"(?P<message>.*)$"
)

# `-v brief`:  I/SomeTag(  1234): the message  (tried before `tag` so the (pid)
# isn't swallowed into the tag).
_BRIEF = re.compile(
    r"^(?P<level>[VDIWEF])/(?P<tag>.*?)\(\s*(?P<pid>\d+)\):\s?"
    r"(?P<message>.*)$"
)

# `-v tag`:  I/SomeTag: the message
_TAG = re.compile(
    r"^(?P<level>[VDIWEF])/(?P<tag>.*?):\s?"
    r"(?P<message>.*)$"
)

# Most-specific first; `brief` must precede `tag` (see above).
_PATTERNS = (_THREADTIME, _TIME, _BRIEF, _TAG)

# The four logcat patterns restated as LogFormat entries, so the built-in and
# user-defined cases are one representation (see core/logformat.py). No level
# aliases: logcat's V/D/I/W/E/F is already canonical.
BUILTIN_LOG_FORMATS: tuple[LogFormat, ...] = (
    LogFormat(name="threadtime", pattern=_THREADTIME.pattern, level_aliases={}, builtin=True),
    LogFormat(name="time", pattern=_TIME.pattern, level_aliases={}, builtin=True),
    LogFormat(name="brief", pattern=_BRIEF.pattern, level_aliases={}, builtin=True),
    LogFormat(name="tag", pattern=_TAG.pattern, level_aliases={}, builtin=True),
)

# Precompiled once at import time, mirroring _PATTERNS exactly — the default
# path (formats=None) must stay byte-identical to before this module gained
# custom-format support, with zero added per-call cost.
_DEFAULT_FORMATS: list[CompiledFormat] = compile_formats(list(BUILTIN_LOG_FORMATS))


def parse_line(line: str, formats: list[CompiledFormat] | None = None) -> LogEntry:
    """Turn one raw logcat line into a LogEntry.

    Tries each format in `formats` (or the four built-in logcat patterns when
    `formats` is None — the original, unchanged behaviour every existing call
    site relies on) in order and builds a LogEntry from whatever fields that
    format provides (absent fields are ""). `formats` must already be
    compiled — compiling a regex per call would be a real cost on a path that
    runs millions of times; callers compile once via `compile_formats` and
    reuse the result. Lines that match nothing (e.g. the "--------- beginning
    of main" banners) are returned with empty fields and the whole line as the
    message, so nothing is silently dropped.
    """
    patterns = formats if formats is not None else _DEFAULT_FORMATS
    for cf in patterns:
        m = cf.regex.match(line)
        if m:
            g = m.groupdict()
            level = apply_aliases(g.get("level") or "", cf.format.level_aliases)
            return LogEntry(
                time=g.get("time") or "",
                pid=g.get("pid") or "",
                tid=g.get("tid") or "",
                level=level,
                tag=(g.get("tag") or "").strip(),
                message=g.get("message") or "",
            )
    return LogEntry(time="", pid="", tid="", level="", tag="", message=line)
