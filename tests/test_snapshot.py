"""Tests for the dumpsys argv builder (pure, no adb/Qt)."""

from zlog.core.snapshot import dumpsys_args


def test_dumpsys_args_full_when_blank():
    assert dumpsys_args("") == ["shell", "dumpsys"]
    assert dumpsys_args("   ") == ["shell", "dumpsys"]


def test_dumpsys_args_single_service():
    assert dumpsys_args("battery") == ["shell", "dumpsys", "battery"]


def test_dumpsys_args_takes_first_token_only():
    # A stray space can't smuggle in a second argument.
    assert dumpsys_args("meminfo com.example") == ["shell", "dumpsys", "meminfo"]
