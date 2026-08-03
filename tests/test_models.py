"""LogEntry's pure, Qt-free helpers."""

from zlog.core.models import LogEntry, all_unparsed


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


def test_all_unparsed_true_when_every_entry_lacks_a_level():
    entries = [LogEntry("t", "1", "1", "", "T", "a"), LogEntry("t", "1", "1", "", "T", "b")]
    assert all_unparsed(entries) is True


def test_all_unparsed_false_when_any_entry_has_a_level():
    entries = [LogEntry("t", "1", "1", "", "T", "a"), LogEntry("t", "1", "1", "I", "T", "b")]
    assert all_unparsed(entries) is False


def test_all_unparsed_false_when_empty():
    assert all_unparsed([]) is False
