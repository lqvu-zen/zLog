"""Tests for the pure autosave rotation helpers. No Qt required."""

from zlog.core.autosave import rotate_path, should_rotate


def test_rotate_path_inserts_one_before_extension():
    assert rotate_path("a.log") == "a.1.log"
    assert rotate_path("/tmp/x/autosave.log") == "/tmp/x/autosave.1.log"
    assert rotate_path("noext") == "noext.1"


def test_should_rotate():
    assert should_rotate(90, 20, cap=100) is True  # 110 > 100
    assert should_rotate(50, 20, cap=100) is False  # 70 <= 100
    assert should_rotate(0, 999, cap=0) is False  # disabled cap never rotates
