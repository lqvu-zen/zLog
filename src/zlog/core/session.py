"""Serialize a log session to/from `adb logcat -v threadtime` text.

Pure functions only — no Qt, no file IO — so they're unit-testable and the saved
files round-trip through the same `parse_line` used for live logs.
"""

from __future__ import annotations

from zlog.core.models import LogEntry
from zlog.core.parser import parse_line


def format_entry(entry: LogEntry) -> str:
    """Render one entry as a threadtime line.

    Unparsed entries (no level — banners and the like) are written as their raw
    text so they survive a round-trip unchanged.
    """
    if not entry.level:
        return entry.message
    return f"{entry.time} {entry.pid} {entry.tid} {entry.level} {entry.tag}: {entry.message}"


def entries_to_text(entries: list[LogEntry]) -> str:
    """Join entries into a newline-terminated text block (empty for no entries)."""
    if not entries:
        return ""
    return "\n".join(format_entry(e) for e in entries) + "\n"


def text_to_entries(text: str) -> list[LogEntry]:
    """Parse saved log text back into entries, reusing the live-log parser."""
    return [parse_line(line) for line in text.splitlines()]
