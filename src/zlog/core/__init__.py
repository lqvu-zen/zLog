"""Pure, framework-free domain logic (no Qt imports here).

Keeping this layer free of Qt means it can be unit-tested without a display
and reused if the UI is ever swapped out.
"""

from zlog.core.models import LEVEL_RANK, LogEntry
from zlog.core.parser import parse_line

__all__ = ["LogEntry", "LEVEL_RANK", "parse_line"]
