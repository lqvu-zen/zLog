"""Tests for `core.dirfollow` — pure, no threads or Qt."""

from __future__ import annotations

import os
import time

from zlog.core.dirfollow import pick_newest, should_switch


def _touch(path, content="x"):
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(content)


def test_no_match_returns_none(tmp_path):
    assert pick_newest(str(tmp_path), "*.log") is None


def test_single_match(tmp_path):
    _touch(tmp_path / "app.log")
    assert pick_newest(str(tmp_path), "*.log") == str(tmp_path / "app.log")


def test_non_matching_files_ignored(tmp_path):
    _touch(tmp_path / "app.log")
    _touch(tmp_path / "notes.txt")
    assert pick_newest(str(tmp_path), "*.log") == str(tmp_path / "app.log")


def test_newest_by_mtime_wins(tmp_path):
    older = tmp_path / "app-1.log"
    newer = tmp_path / "app-2.log"
    _touch(older)
    # Force a distinct, later mtime rather than relying on real-time gaps
    # between two writes on a fast filesystem.
    now = time.time()
    os.utime(older, (now - 10, now - 10))
    _touch(newer)
    os.utime(newer, (now, now))
    assert pick_newest(str(tmp_path), "app-*.log") == str(newer)


def test_tie_breaks_on_lexicographically_largest_name(tmp_path):
    a = tmp_path / "app-a.log"
    b = tmp_path / "app-b.log"
    _touch(a)
    _touch(b)
    now = time.time()
    os.utime(a, (now, now))
    os.utime(b, (now, now))  # identical mtime, on purpose
    assert pick_newest(str(tmp_path), "app-*.log") == str(b)


def test_should_switch_grace_period():
    assert should_switch(old_file_stable_for=0.1, threshold=0.5) is False
    assert should_switch(old_file_stable_for=0.5, threshold=0.5) is True
    assert should_switch(old_file_stable_for=1.0, threshold=0.5) is True
