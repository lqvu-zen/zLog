"""Tests for the pure parsing layer. No Qt or display required."""

from zlog.core.models import LogEntry
from zlog.core.parser import parse_line


def test_parses_standard_threadtime_line():
    line = "06-30 12:34:56.789  1234  5678 I ActivityManager: Start proc"
    entry = parse_line(line)
    assert entry == LogEntry(
        time="06-30 12:34:56.789",
        pid="1234",
        tid="5678",
        level="I",
        tag="ActivityManager",
        message="Start proc",
    )


def test_level_rank_orders_severity():
    assert (
        parse_line("06-30 12:00:00.000 1 1 E Tag: boom").rank
        > parse_line("06-30 12:00:00.000 1 1 I Tag: ok").rank
    )


def test_unparsed_line_keeps_full_text_in_message():
    line = "--------- beginning of main"
    entry = parse_line(line)
    assert entry.level == ""
    assert entry.message == line
    assert entry.rank == 0


def test_tag_with_spaces_is_trimmed():
    entry = parse_line("06-30 12:34:56.789 1 1 W My Tag : something")
    assert entry.level == "W"
    assert entry.tag == "My Tag"
    assert entry.message == "something"


def test_empty_message_is_allowed():
    entry = parse_line("06-30 12:34:56.789 1 1 D Tag: ")
    assert entry.level == "D"
    assert entry.message == ""
