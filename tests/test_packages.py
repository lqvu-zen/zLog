"""Tests for package/PID parsing. No Qt, no adb, no display required."""

from zlog.core.packages import parse_packages, parse_pids


def test_parse_pids_single():
    assert parse_pids("1287\n") == ["1287"]


def test_parse_pids_multiple_processes():
    assert parse_pids("1287 1342 1500\n") == ["1287", "1342", "1500"]


def test_parse_pids_empty_when_not_running():
    assert parse_pids("") == []
    assert parse_pids("\n") == []


def test_parse_packages_strips_prefix_and_sorts():
    out = "package:com.example.beta\npackage:com.example.alpha\n"
    assert parse_packages(out) == ["com.example.alpha", "com.example.beta"]


def test_parse_packages_ignores_blank_and_junk_lines():
    out = "\npackage:com.x\nnot a package line\npackage:\n"
    assert parse_packages(out) == ["com.x"]
