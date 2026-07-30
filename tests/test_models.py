"""LogEntry's pure, Qt-free helpers."""

from zlog.core.models import LogEntry


def _entry(pid="", tid=""):
    return LogEntry("t", pid, tid, "I", "T", "msg")


def test_pidtid_joins_both_when_present():
    assert _entry("100", "200").pidtid == "100-200"


def test_pidtid_falls_back_to_pid_only():
    assert _entry("100", "").pidtid == "100"


def test_pidtid_falls_back_to_tid_only():
    assert _entry("", "200").pidtid == "200"


def test_pidtid_empty_when_neither_present():
    assert _entry("", "").pidtid == ""
