"""Tests for process-start detection. No Qt, no display required."""

from zlog.core.proc import parse_proc_start


def test_modern_format():
    msg = "Start proc 12345:com.example.app/u0a123 for activity com.example/.Main"
    assert parse_proc_start(msg) == ("12345", "com.example.app")


def test_legacy_format():
    msg = "Start proc com.example.app for activity com.example/.Main: pid=678 uid=10012"
    assert parse_proc_start(msg) == ("678", "com.example.app")


def test_non_start_line_returns_none():
    assert parse_proc_start("nothing here") is None
    assert parse_proc_start("FATAL EXCEPTION: main") is None


def test_incomplete_start_line_returns_none():
    assert parse_proc_start("Start proc with no pid or package") is None
