"""Windows debug-output capture wired into the window. Off Windows it must report
gracefully and not start anything; the action exists either way."""

from __future__ import annotations

import sys

import pytest


@pytest.fixture
def window(qapp, tmp_path, monkeypatch):
    from zlog.ui.main_window import MainWindow

    monkeypatch.setattr(MainWindow, "_settings_path", lambda self: tmp_path / "s.json")
    return MainWindow()


def test_capture_action_exists(window):
    assert window.capture_debug_act is not None


def test_capture_off_windows_is_graceful(window):
    window.capture_debug_output()
    if sys.platform != "win32":
        assert window._active.reader is None  # nothing started
        assert "Windows" in window.statusBar().currentMessage()
