"""Parse raw logcat text into LogEntry objects.

Pure functions only — no Qt, no I/O — so this is trivially unit-testable.

We stream with `-v threadtime`, but opened log files may be captured in another
format, so `parse_line` recognizes the common ones (threadtime, time, brief, tag)
and falls back to the raw line for anything else (banners, wrapped output), so
nothing is silently dropped.
"""

from __future__ import annotations

import re

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


def parse_line(line: str) -> LogEntry:
    """Turn one raw logcat line into a LogEntry.

    Tries each known logcat format in order and builds a LogEntry from whatever
    fields that format provides (absent fields are ""). Lines that match nothing
    (e.g. the "--------- beginning of main" banners) are returned with empty
    fields and the whole line as the message, so nothing is silently dropped.
    """
    for pattern in _PATTERNS:
        m = pattern.match(line)
        if m:
            g = m.groupdict()
            return LogEntry(
                time=g.get("time") or "",
                pid=g.get("pid") or "",
                tid=g.get("tid") or "",
                level=g.get("level") or "",
                tag=(g.get("tag") or "").strip(),
                message=g.get("message") or "",
            )
    return LogEntry(time="", pid="", tid="", level="", tag="", message=line)
