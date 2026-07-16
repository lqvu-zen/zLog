"""Crash/ANR detection over parsed log lines.

Matches on the message text alone (not tag) since native crashes, Java crashes,
and ANRs surface under different tags across OEMs and Android versions, but the
message markers themselves are stable.
"""

from __future__ import annotations

import re
from collections import Counter

from zlog.core.models import LogEntry

_CRASH_RE = re.compile(r"FATAL EXCEPTION|Fatal signal \d+")
_ANR_RE = re.compile(r"ANR in ")


def classify_incident(entry: LogEntry) -> str | None:
    """Return "crash", "anr", or None for a parsed log entry."""
    if _CRASH_RE.search(entry.message):
        return "crash"
    if _ANR_RE.search(entry.message):
        return "anr"
    return None


def format_incident_summary(counts: Counter) -> str:
    """Render e.g. "2 crashes, 1 ANR"; empty string when there are none."""
    parts = []
    crashes = counts.get("crash", 0)
    if crashes:
        parts.append(f"{crashes} crash{'es' if crashes != 1 else ''}")
    anrs = counts.get("anr", 0)
    if anrs:
        parts.append(f"{anrs} ANR{'s' if anrs != 1 else ''}")
    return ", ".join(parts)
