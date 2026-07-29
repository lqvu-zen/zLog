"""Windows Event Log capture wired into the window. Off Windows it must report
gracefully and not start anything; the action exists either way. The reader
itself is stubbed here (see test_evtlog_reader.py for its own coverage) so
these tests never touch the real Event Log or pywin32."""

from __future__ import annotations

import pytest
from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QInputDialog


class _StubReader(QObject):
    """Same signal surface as EventLogReader/DebugOutputReader."""

    batch_ready = Signal(list)
    error = Signal(str)

    def __init__(self, channel, backfill=200, parent=None):
        super().__init__(parent)
        self.channel = channel
        self.serial = ""
        self.started = False

    def start(self):
        self.started = True

    def isRunning(self):
        return False

    def stop(self):
        pass


@pytest.fixture
def window(qapp, tmp_path, monkeypatch):
    from zlog.ui.main_window import MainWindow

    monkeypatch.setattr(MainWindow, "_settings_path", lambda self: tmp_path / "s.json")
    return MainWindow()


def test_capture_event_log_action_exists(window):
    assert window.capture_evtlog_act is not None


def test_capture_when_not_supported_is_graceful(window, monkeypatch):
    # Forces the "unsupported" branch deterministically (real sys.platform
    # would make this a no-op check on a Windows test runner) — crucially,
    # this must return *before* the channel-picker dialog, or a real
    # QInputDialog.exec() would block forever under the offscreen platform.
    import zlog.winlog.evtlog_reader as evtlog_reader

    monkeypatch.setattr(evtlog_reader, "is_supported", lambda: False)
    window.capture_event_log()
    assert window._active.reader is None  # nothing started
    assert "Windows" in window.statusBar().currentMessage()


def test_capture_event_log_cancelled_dialog_starts_nothing(window, monkeypatch):
    import zlog.winlog.evtlog_reader as evtlog_reader

    monkeypatch.setattr(evtlog_reader, "is_supported", lambda: True)
    monkeypatch.setattr(evtlog_reader, "EventLogReader", _StubReader)
    monkeypatch.setattr(QInputDialog, "getItem", lambda *a, **k: ("Application", False))
    window.capture_event_log()
    assert window._active.reader is None


def test_capture_event_log_attaches_reader_and_labels_tab(window, monkeypatch):
    import zlog.winlog.evtlog_reader as evtlog_reader

    monkeypatch.setattr(evtlog_reader, "is_supported", lambda: True)
    monkeypatch.setattr(evtlog_reader, "EventLogReader", _StubReader)
    monkeypatch.setattr(QInputDialog, "getItem", lambda *a, **k: ("System", True))
    window.capture_event_log()
    assert window._active.reader is not None
    assert isinstance(window._active.reader, _StubReader)
    assert window._active.reader.channel == "System"
    assert window._active.reader.started
    assert window._active.stream_label == "Event Log: System"
    assert window.stop_btn.isEnabled()
    assert "System" in window.statusBar().currentMessage()


def test_capture_event_log_blank_typed_channel_starts_nothing(window, monkeypatch):
    import zlog.winlog.evtlog_reader as evtlog_reader

    monkeypatch.setattr(evtlog_reader, "is_supported", lambda: True)
    monkeypatch.setattr(evtlog_reader, "EventLogReader", _StubReader)
    monkeypatch.setattr(QInputDialog, "getItem", lambda *a, **k: ("   ", True))
    window.capture_event_log()
    assert window._active.reader is None
