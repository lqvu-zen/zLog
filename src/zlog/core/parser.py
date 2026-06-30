"""Parse raw logcat text into LogEntry objects.

Pure functions only — no Qt, no I/O — so this is trivially unit-testable.
"""

from __future__ import annotations

import re

from zlog.core.models import LogEntry

# Matches the default `adb logcat -v threadtime` format:
#   06-30 12:34:56.789  1234  5678 I SomeTag : the message
_THREADTIME = re.compile(
    r"^(?P<time>\d\d-\d\d \d\d:\d\d:\d\d\.\d+)\s+"
    r"(?P<pid>\d+)\s+(?P<tid>\d+)\s+"
    r"(?P<level>[VDIWEF])\s+"
    r"(?P<tag>.*?):\s?"
    r"(?P<message>.*)$"
)


def parse_line(line: str) -> LogEntry:
    """Turn one raw logcat line into a LogEntry.

    Lines that don't match the expected format (e.g. the
    "--------- beginning of main" banners) are returned with empty fields
    and the whole line as the message, so nothing is silently dropped.
    """
    m = _THREADTIME.match(line)
    if m:
        return LogEntry(
            time=m.group("time"),
            pid=m.group("pid"),
            tid=m.group("tid"),
            level=m.group("level"),
            tag=m.group("tag").strip(),
            message=m.group("message"),
        )
    return LogEntry(time="", pid="", tid="", level="", tag="", message=line)
