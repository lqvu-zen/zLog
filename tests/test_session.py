"""Tests for session save/load serialization. No Qt, no IO, no display."""

from zlog.core.models import LogEntry
from zlog.core.session import entries_to_text, text_to_entries


def test_round_trip_parsed_entries():
    entries = [
        LogEntry("06-30 12:34:56.789", "1234", "5678", "I", "ActivityManager", "Start proc"),
        LogEntry("06-30 12:34:56.800", "1234", "5679", "E", "AndroidRuntime", "FATAL: boom"),
    ]
    assert text_to_entries(entries_to_text(entries)) == entries


def test_unparsed_line_round_trips():
    banner = LogEntry("", "", "", "", "", "--------- beginning of main")
    assert text_to_entries(entries_to_text([banner])) == [banner]


def test_message_with_colons_round_trips():
    entry = LogEntry("06-30 12:00:00.000", "1", "1", "W", "Tag", "a: b: c")
    assert text_to_entries(entries_to_text([entry])) == [entry]


def test_empty():
    assert entries_to_text([]) == ""
    assert text_to_entries("") == []


def test_line_shape():
    entry = LogEntry("06-30 12:34:56.789", "1234", "5678", "I", "Tag", "msg")
    assert entries_to_text([entry]).rstrip("\n") == "06-30 12:34:56.789 1234 5678 I Tag: msg"
