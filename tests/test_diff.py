"""Tests for the pure capture-diff. No Qt required."""

from zlog.core.diff import diff_logs, line_key
from zlog.core.models import LogEntry


def test_line_key_ignores_time_and_pid():
    a = LogEntry("12:00:00.000", "1", "2", "E", "Boom", "crash")
    b = LogEntry("13:59:59.999", "999", "888", "E", "Boom", "crash")
    assert line_key(a) == line_key(b) == "E/Boom: crash"


def test_diff_marks_equal_delete_insert():
    a = ["x", "y", "z"]
    b = ["x", "w", "z"]
    ops = diff_logs(a, b)
    # x equal, y->w replace (delete y, insert w), z equal
    assert (" ", "x") in ops
    assert ("-", "y") in ops
    assert ("+", "w") in ops
    assert (" ", "z") in ops


def test_identical_is_all_context():
    a = ["a", "b"]
    assert diff_logs(a, list(a)) == [(" ", "a"), (" ", "b")]


def test_empty_sides():
    assert diff_logs([], ["a"]) == [("+", "a")]
    assert diff_logs(["a"], []) == [("-", "a")]
