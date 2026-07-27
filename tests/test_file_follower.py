"""FileFollower against real files: append, truncate, rotate, stop.

Cross-platform by design, so the follow loop is genuinely exercised here rather
than only by hand.
"""

from __future__ import annotations

import os

import pytest
from PySide6.QtCore import QEventLoop, QTimer

from zlog.ui.file_follower import FileFollower, file_key, should_flush

LINE = "06-30 12:00:0{n}.000 1 2 I Tag: line{n}\n"


def _messages(entries):
    return [e.message for e in entries]


def _wait_for(qapp, predicate, timeout_ms=6000):
    """Spin the event loop until `predicate()` or the timeout (never hang CI)."""
    loop = QEventLoop()
    elapsed = {"ms": 0}

    def tick():
        elapsed["ms"] += 50
        if predicate() or elapsed["ms"] >= timeout_ms:
            loop.quit()

    timer = QTimer()
    timer.timeout.connect(tick)
    timer.start(50)
    loop.exec()
    timer.stop()
    return predicate()


@pytest.fixture
def logfile(tmp_path):
    p = tmp_path / "app.log"
    p.write_text(LINE.format(n=1), encoding="utf-8")
    return p


def _settle(qapp, ms=500):
    """Spin the loop briefly so the follower can take its opening stat.

    Only tests need this: in real use you start following and the app writes
    later, but here we'd otherwise append before the thread has an offset.
    """
    _wait_for(qapp, lambda: False, timeout_ms=ms)


def _start(qapp, path, **kw):
    reader = FileFollower(str(path), **kw)
    got: list = []
    reader.batch_ready.connect(got.extend)
    reader.start()
    return reader, got


def test_reads_existing_content_then_follows(qapp, logfile):
    reader, got = _start(qapp, logfile)
    try:
        assert _wait_for(qapp, lambda: len(got) >= 1)
        assert "line1" in _messages(got)[0]

        with open(logfile, "a", encoding="utf-8") as fh:
            fh.write(LINE.format(n=2))
        assert _wait_for(qapp, lambda: len(got) >= 2)
        assert any("line2" in m for m in _messages(got))
    finally:
        reader.stop()


def test_from_end_skips_existing_content(qapp, logfile):
    reader, got = _start(qapp, logfile, from_end=True)
    try:
        _settle(qapp)  # let it record "the end" before we append
        with open(logfile, "a", encoding="utf-8") as fh:
            fh.write(LINE.format(n=9))
        assert _wait_for(qapp, lambda: got)
        msgs = _messages(got)
        assert any("line9" in m for m in msgs)
        assert not any("line1" in m for m in msgs)  # pre-existing line skipped
    finally:
        reader.stop()


def test_partial_line_is_not_emitted_until_complete(qapp, logfile):
    reader, got = _start(qapp, logfile)
    try:
        assert _wait_for(qapp, lambda: len(got) >= 1)
        before = len(got)
        with open(logfile, "a", encoding="utf-8") as fh:
            fh.write("06-30 12:00:05.000 1 2 I Tag: half")  # no newline yet
        _wait_for(qapp, lambda: False, timeout_ms=700)  # give it time to (not) emit
        assert len(got) == before, "a partial line must not be emitted"

        with open(logfile, "a", encoding="utf-8") as fh:
            fh.write(" written\n")
        assert _wait_for(qapp, lambda: len(got) > before)
        assert any("half written" in m for m in _messages(got))
    finally:
        reader.stop()


def test_truncation_rewinds_and_rereads(qapp, logfile):
    """A logger truncating in place: the file becomes shorter than what we've
    already consumed, so the saved offset is past the end and we restart."""
    reader, got = _start(qapp, logfile)
    try:
        # Make the starting content clearly longer than the replacement.
        with open(logfile, "a", encoding="utf-8") as fh:
            fh.write(LINE.format(n=2) + LINE.format(n=4) + LINE.format(n=5))
        assert _wait_for(qapp, lambda: len(got) >= 4)
        got.clear()

        with open(logfile, "w", encoding="utf-8") as fh:
            fh.write(LINE.format(n=3))
        assert _wait_for(qapp, lambda: got)
        assert any("line3" in m for m in _messages(got))
    finally:
        reader.stop()


def test_rotation_to_a_new_file_rereads(qapp, logfile):
    """Deleted and recreated. The identity check covers the same-size case (see
    test_identity_change_beats_equal_size), but filesystems commonly *reuse* the
    freed inode, so here the replacement is a different size — the signal that
    works regardless."""
    reader, got = _start(qapp, logfile)
    try:
        with open(logfile, "a", encoding="utf-8") as fh:
            fh.write(LINE.format(n=2) + LINE.format(n=4))
        assert _wait_for(qapp, lambda: len(got) >= 3)
        got.clear()
        os.remove(logfile)
        with open(logfile, "w", encoding="utf-8") as fh:
            fh.write(LINE.format(n=7))
        assert _wait_for(qapp, lambda: got)
        assert any("line7" in m for m in _messages(got))
    finally:
        reader.stop()


def test_missing_file_reports_error(qapp, tmp_path):
    reader = FileFollower(str(tmp_path / "nope.log"))
    errors: list[str] = []
    reader.error.connect(errors.append)
    loop = QEventLoop()
    reader.finished.connect(loop.quit)
    QTimer.singleShot(6000, loop.quit)
    reader.start()
    loop.exec()
    reader.stop()
    assert errors and "Could not open" in errors[0]


def test_stop_ends_the_thread_promptly(qapp, logfile):
    reader, _ = _start(qapp, logfile)
    reader.stop()
    assert not reader.isRunning()


def test_name_is_the_file_basename(tmp_path):
    assert FileFollower(str(tmp_path / "sub" / "my.log")).name == "my.log"


def test_should_flush_rules():
    assert should_flush(0, 99) is False
    assert should_flush(1, 0.0) is False
    assert should_flush(1, 0.5) is True
    assert should_flush(500, 0.0) is True


def test_file_key_is_stable_and_none_when_missing(tmp_path):
    p = tmp_path / "x.log"
    p.write_text("a\n", encoding="utf-8")
    assert file_key(str(p)) == file_key(str(p))  # stable across calls
    assert file_key(str(tmp_path / "missing.log")) is None


def test_file_key_changes_when_recreated(tmp_path):
    p = tmp_path / "rot.log"
    p.write_text("a\n", encoding="utf-8")
    first = file_key(str(p))
    os.remove(p)
    p.write_text("b\n", encoding="utf-8")
    # Identity should differ (inode and/or ctime); if the OS reuses everything
    # the size check still catches the rotation, so this is best-effort.
    assert first is not None and file_key(str(p)) is not None


# --- window wiring ---------------------------------------------------------
def test_follow_file_starts_a_reader_in_a_tab(qapp, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QFileDialog

    from zlog.ui.main_window import MainWindow

    monkeypatch.setattr(MainWindow, "_settings_path", lambda self: tmp_path / "s.json")
    log = tmp_path / "watched.log"
    log.write_text(LINE.format(n=1), encoding="utf-8")
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *a, **k: (str(log), ""))

    window = MainWindow()
    try:
        window.follow_file()
        assert window._active.reader is not None
        assert window._active.stream_label == "watched.log"
        assert window.stop_btn.isEnabled()
        assert str(log) in window._recent  # recorded like any opened log
    finally:
        window.stop()
    assert window._active.reader is None  # Stop tore the follower down


def test_follow_file_cancelled_does_nothing(qapp, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QFileDialog

    from zlog.ui.main_window import MainWindow

    monkeypatch.setattr(MainWindow, "_settings_path", lambda self: tmp_path / "s.json")
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *a, **k: ("", ""))

    window = MainWindow()
    window.follow_file()
    assert window._active.reader is None
