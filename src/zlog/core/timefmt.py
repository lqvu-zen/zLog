"""Format logcat timestamps as absolute / elapsed / delta — pure, no Qt.

`adb logcat -v threadtime` stamps lines `MM-DD HH:MM:SS.mmm` with no year, so we
parse to a datetime with a fixed (arbitrary but consistent) year. Elapsed/delta
are then just datetime subtraction. A capture that crosses a year boundary would
mis-order — acceptable for a log session and documented here.
"""

from __future__ import annotations

from datetime import datetime, timedelta

_FMT = "%m-%d %H:%M:%S.%f"


def parse_logcat_time(s: str) -> datetime | None:
    """Parse a threadtime stamp to a datetime, or None if it doesn't match."""
    if not s:
        return None
    try:
        return datetime.strptime(s, _FMT)
    except ValueError:
        return None


def format_delta(td: timedelta) -> str:
    """Format a signed duration compactly: +0.750, +1:23.450, +1:01:01.500."""
    total = td.total_seconds()
    sign = "-" if total < 0 else "+"
    total = abs(total)
    hours = int(total // 3600)
    minutes = int((total % 3600) // 60)
    seconds = total - hours * 3600 - minutes * 60
    if hours:
        return f"{sign}{hours}:{minutes:02d}:{seconds:06.3f}"
    if minutes:
        return f"{sign}{minutes}:{seconds:06.3f}"
    return f"{sign}{seconds:.3f}"
