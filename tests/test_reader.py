"""Tests for the adb logcat command builder (pure part of AdbReader)."""

from zlog.adb.reader import build_logcat_command


def test_default():
    assert build_logcat_command("adb", None) == ["adb", "logcat", "-v", "threadtime"]


def test_serial():
    assert build_logcat_command("adb", "ABC123") == [
        "adb",
        "-s",
        "ABC123",
        "logcat",
        "-v",
        "threadtime",
    ]


def test_buffers_and_bad_names_dropped():
    cmd = build_logcat_command("adb", None, ["main", "radio", "bogus"])
    assert cmd == ["adb", "logcat", "-v", "threadtime", "-b", "main", "-b", "radio"]
