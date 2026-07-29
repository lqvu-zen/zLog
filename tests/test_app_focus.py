"""Launch-app dialog and its window wiring (offscreen Qt)."""

from __future__ import annotations

import sys

import pytest


@pytest.fixture
def window(qapp, tmp_path, monkeypatch):
    from zlog.ui.main_window import MainWindow

    monkeypatch.setattr(MainWindow, "_settings_path", lambda self: tmp_path / "s.json")
    return MainWindow()


# --- launch dialog --------------------------------------------------------
def test_launch_dialog_values_and_ok_gating(qapp):
    from PySide6.QtWidgets import QDialogButtonBox

    from zlog.ui.launch_dialog import LaunchDialog

    dlg = LaunchDialog()
    ok = dlg.buttons.button(QDialogButtonBox.Ok)
    assert ok.isEnabled() is False  # no program yet
    dlg.exe_edit.setText(" app.exe ")
    dlg.args_edit.setText(" --v ")
    assert ok.isEnabled() is True
    assert dlg.get_values() == ("app.exe", "--v", "")


def test_launch_dialog_prefills(qapp):
    from zlog.ui.launch_dialog import LaunchDialog

    dlg = LaunchDialog("a.exe", "--x", "/tmp")
    assert dlg.get_values() == ("a.exe", "--x", "/tmp")


# --- window wiring --------------------------------------------------------
def test_launch_app_starts_reader_and_focuses(window, monkeypatch):
    from PySide6.QtWidgets import QDialog

    import zlog.ui.launch_dialog as ld

    class FakeDialog:
        def __init__(self, *a, **k):
            pass

        def exec(self):
            return QDialog.Accepted

        def get_values(self):
            return (sys.executable, "-c \"print('hi')\"", "")

    monkeypatch.setattr(ld, "LaunchDialog", FakeDialog)
    window.launch_app()
    try:
        assert window._active.reader is not None
        assert window._active.stream_label  # tab labeled by the exe name
        assert "proc:" in window.query.text()  # focused on the launched app
        assert window._last_launch[0] == sys.executable  # remembered for next time
    finally:
        window.stop()
    assert window._active.reader is None  # Stop tore the child down


def test_launch_app_button_exists(window):
    assert window.launch_app_btn is not None
    assert window.launch_app_btn.text() == "Launch App…"
    assert window.launch_app_act is not None


def test_launch_app_btn_triggers_launch_app(qapp, tmp_path, monkeypatch):
    from zlog.ui.main_window import MainWindow

    monkeypatch.setattr(MainWindow, "_settings_path", lambda self: tmp_path / "s.json")
    called = []
    monkeypatch.setattr(MainWindow, "launch_app", lambda self: called.append(True))
    win = MainWindow()
    win.launch_app_btn.click()
    assert called == [True]
