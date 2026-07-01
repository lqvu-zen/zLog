"""Pure, framework-free domain logic (no Qt imports here).

Keeping this layer free of Qt means it can be unit-tested without a display
and reused if the UI is ever swapped out.
"""

from zlog.core.devices import Device, parse_devices
from zlog.core.models import LEVEL_RANK, LogEntry
from zlog.core.packages import parse_packages, parse_pids
from zlog.core.parser import parse_line
from zlog.core.proc import parse_proc_start
from zlog.core.search import compile_matcher
from zlog.core.session import entries_to_text, text_to_entries

__all__ = [
    "LogEntry",
    "LEVEL_RANK",
    "parse_line",
    "parse_proc_start",
    "Device",
    "parse_devices",
    "parse_pids",
    "parse_packages",
    "compile_matcher",
    "entries_to_text",
    "text_to_entries",
]
