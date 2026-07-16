"""Tests for the Choreographer jank aggregator — pure, no Qt."""

from zlog.core.jank import jank_summary
from zlog.core.models import LogEntry


def _entry(tag="Choreographer", message="Skipped 5 frames!", pid="100"):
    return LogEntry("12:00:00.000", pid, "200", "W", tag, message)


def test_aggregates_by_pid():
    entries = [
        _entry(pid="100", message="Skipped 5 frames!"),
        _entry(pid="100", message="Skipped 10 frames!"),
        _entry(pid="200", message="Skipped 3 frames!"),
    ]
    rows = jank_summary(entries)
    assert rows == [("100", 2, 15), ("200", 1, 3)]  # sorted by total frames desc


def test_ignores_non_choreographer_lines():
    entries = [_entry(tag="ActivityManager", message="Skipped 5 frames!")]
    assert jank_summary(entries) == []


def test_ignores_choreographer_lines_without_skip_pattern():
    entries = [_entry(message="Frame rate is normal")]
    assert jank_summary(entries) == []


def test_empty_input():
    assert jank_summary([]) == []


def test_sort_ties_broken_by_pid_ascending():
    entries = [
        _entry(pid="200", message="Skipped 5 frames!"),
        _entry(pid="100", message="Skipped 5 frames!"),
    ]
    assert jank_summary(entries) == [("100", 1, 5), ("200", 1, 5)]
