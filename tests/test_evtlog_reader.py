"""What's testable of the Event Log reader off Windows: it imports cleanly,
reports non-Windows gracefully, and its pure helpers are correct. The
subscribe/backfill loop itself is Windows-only and covered manually."""

from __future__ import annotations

import sys

from zlog.winlog.channels import DEFAULT_CHANNELS
from zlog.winlog.evtlog_reader import is_supported, should_flush


def test_module_imports_without_windows(qapp):
    # The import above already proves no Win32 symbols are needed at import
    # time; instantiating the class must likewise not touch pywin32.
    from zlog.winlog.evtlog_reader import EventLogReader

    r = EventLogReader("Application")
    assert r.channel == "Application"
    assert r.backfill == 200
    assert r.serial == ""


def test_is_supported_matches_platform():
    assert is_supported() == (sys.platform == "win32")


def test_should_flush_rules():
    assert should_flush(0, 999) is False  # nothing pending
    assert should_flush(1, 0.0) is False  # below both caps
    assert should_flush(1, 0.3) is True  # time cap
    assert should_flush(200, 0.0) is True  # size cap


def test_default_channels_are_sane():
    assert "Application" in DEFAULT_CHANNELS
    assert "System" in DEFAULT_CHANNELS


def test_reports_cleanly_without_pywin32(qapp, monkeypatch):
    """Whether pywin32 truly isn't installed (off-Windows, most CI) or is
    unavailable for some other reason on real Windows, starting the reader
    must report an error rather than crash the thread. Forces the "missing"
    case deterministically via sys.modules rather than depending on whether
    pywin32 happens to be installed in this environment."""
    from PySide6.QtCore import QEventLoop, QTimer

    from zlog.winlog.evtlog_reader import EventLogReader

    monkeypatch.setitem(sys.modules, "win32evtlog", None)
    monkeypatch.setitem(sys.modules, "win32event", None)
    reader = EventLogReader("Application")
    errors: list[str] = []
    reader.error.connect(errors.append)
    loop = QEventLoop()
    reader.finished.connect(loop.quit)
    QTimer.singleShot(5000, loop.quit)
    reader.start()
    loop.exec()
    assert len(errors) == 1
    assert "Windows" in errors[0] or "unavailable" in errors[0]
