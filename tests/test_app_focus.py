"""Focus-app picker, launch dialog, and their window wiring (offscreen Qt)."""

from __future__ import annotations

import sys

import pytest

from zlog.core.procinfo import ProcessInfo

PROCS = [ProcessInfo(10, "alpha.exe"), ProcessInfo(20, "beta.exe")]


@pytest.fixture
def window(qapp, tmp_path, monkeypatch):
    from zlog.ui.main_window import MainWindow

    monkeypatch.setattr(MainWindow, "_settings_path", lambda self: tmp_path / "s.json")
    return MainWindow()


# --- process picker dialog ------------------------------------------------
def test_picker_lists_injected_processes(qapp):
    from zlog.ui.process_dialog import ProcessPickerDialog

    dlg = ProcessPickerDialog(PROCS)
    assert dlg.list.count() == 2
    assert dlg.list.item(0).text() == "alpha.exe (10)"


def test_picker_search_narrows(qapp):
    from zlog.ui.process_dialog import ProcessPickerDialog

    dlg = ProcessPickerDialog(PROCS)
    dlg.search.setText("beta")
    assert dlg.list.count() == 1
    assert dlg.list.item(0).text() == "beta.exe (20)"


def test_picker_selected_returns_process(qapp):
    from zlog.ui.process_dialog import ProcessPickerDialog

    dlg = ProcessPickerDialog(PROCS)
    dlg.list.setCurrentRow(1)
    assert dlg.selected().pid == 20
    assert dlg.focus_by_pid() is False  # name-focus is the default


def test_picker_empty_state(qapp):
    from zlog.ui.process_dialog import ProcessPickerDialog

    dlg = ProcessPickerDialog([])
    assert dlg.list.count() == 0
    assert dlg.empty_label.isVisibleTo(dlg)


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
def test_focus_app_sets_query_by_name(window, monkeypatch):
    from PySide6.QtWidgets import QDialog

    import zlog.ui.process_dialog as pd

    class FakeDialog:
        def __init__(self, *a, **k):
            pass

        def exec(self):
            return QDialog.Accepted

        def selected(self):
            return ProcessInfo(77, "target.exe")

        def focus_by_pid(self):
            return False

    monkeypatch.setattr(pd, "ProcessPickerDialog", FakeDialog)
    window.query.setText("level:E")
    window.focus_app()
    assert window.query.text() == "level:E proc:target.exe"
    assert window.package_box.currentText() == "target.exe"  # same path as Apply


def test_focus_app_by_pid_option(window, monkeypatch):
    from PySide6.QtWidgets import QDialog

    import zlog.ui.process_dialog as pd

    class FakeDialog:
        def __init__(self, *a, **k):
            pass

        def exec(self):
            return QDialog.Accepted

        def selected(self):
            return ProcessInfo(77, "target.exe")

        def focus_by_pid(self):
            return True

    monkeypatch.setattr(pd, "ProcessPickerDialog", FakeDialog)
    window.focus_app()
    assert window.query.text() == "pid:77"


def test_focus_app_cancel_leaves_query(window, monkeypatch):
    from PySide6.QtWidgets import QDialog

    import zlog.ui.process_dialog as pd

    class FakeDialog:
        def __init__(self, *a, **k):
            pass

        def exec(self):
            return QDialog.Rejected

        def selected(self):
            return None

        def focus_by_pid(self):
            return False

    monkeypatch.setattr(pd, "ProcessPickerDialog", FakeDialog)
    window.query.setText("tag:Net")
    window.focus_app()
    assert window.query.text() == "tag:Net"


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


def test_focus_app_button_exists(window):
    assert window.focus_app_btn is not None
    assert window.focus_app_btn.text() == "Browse…"
    assert window.launch_app_act is not None
