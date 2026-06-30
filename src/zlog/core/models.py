"""Core data types shared across the app."""

from __future__ import annotations

from dataclasses import dataclass

# Numeric rank per logcat level so "show Warning and above" is a >= compare.
LEVEL_RANK: dict[str, int] = {"V": 0, "D": 1, "I": 2, "W": 3, "E": 4, "F": 5}


@dataclass(frozen=True, slots=True)
class LogEntry:
    """One parsed logcat line."""

    time: str  # "06-30 12:34:56.789"
    pid: str  # process id
    tid: str  # thread id
    level: str  # V D I W E F (Verbose..Fatal), or "" if unparsed
    tag: str  # the log tag
    message: str  # the actual text

    @property
    def rank(self) -> int:
        """Severity rank; unparsed lines (level == '') rank as 0."""
        return LEVEL_RANK.get(self.level, 0)
