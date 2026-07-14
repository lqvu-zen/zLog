"""Tests for the Settings dialog (view) and MainWindow apply round-trip."""

from __future__ import annotations

import pytest

_OPTS = dict(
    themes=["Light", "Dark"],
    time_modes=[("Absolute", "absolute"), ("Since start", "since_start"), ("Delta", "delta")],
    tail_options=[("Whole buffer", 0), ("Last 500", 500)],
    max_options=[("Unlimited", 0), ("10,000 lines", 10000)],
    buffers=["main", "system", "crash"],
)


def test_dialog_reflects_initial_values(qapp):
    from zlog.ui.settings_dialog import SettingsDialog

    values = {
        "theme": "Dark",
        "font_delta": 3,
        "show_details": False,
        "time_mode": "delta",
        "highlight": True,
        "case": True,
        "collapse": True,
        "show_process": True,
        "buffers": {"system"},
        "tail": 500,
        "max_rows": 10000,
        "clear_on_start": True,
        "follow": False,
        "reopen_last": True,
        "autosave": True,
    }
    dlg = SettingsDialog(values, **_OPTS)
    assert dlg.get_values() == values  # every control round-trips its value


def test_dialog_defaults_when_values_missing(qapp):
    from zlog.ui.settings_dialog import SettingsDialog

    dlg = SettingsDialog({}, **_OPTS)
    got = dlg.get_values()
    assert got["theme"] == "Light" and got["time_mode"] == "absolute"
    assert got["buffers"] == set() and got["max_rows"] == 0


@pytest.fixture
def window(qapp, tmp_path, monkeypatch):
    from zlog.ui.main_window import MainWindow

    monkeypatch.setattr(MainWindow, "_settings_path", lambda self: tmp_path / "s.json")
    monkeypatch.setattr(MainWindow, "_refresh_process_map", lambda self: None)
    return MainWindow()


def test_apply_settings_values_drives_state(window):
    v = window._collect_settings()
    v.update(
        theme="Dark",
        show_process=True,
        collapse=True,
        time_mode="delta",
        max_rows=10000,
        font_delta=2,
        clear_on_start=True,
    )
    window._apply_settings_values(v)
    assert window._theme_name == "Dark"
    assert window.process_action.isChecked() is True
    assert window.collapse_action.isChecked() is True
    assert window._time_actions["delta"].isChecked() is True
    assert window._max_rows_actions[10000].isChecked() is True
    assert window._font_delta == 2
    assert window.clear_on_start_action.isChecked() is True


def test_settings_survive_relaunch_via_apply(qapp, tmp_path, monkeypatch):
    from zlog.ui.main_window import MainWindow

    monkeypatch.setattr(MainWindow, "_settings_path", lambda self: tmp_path / "s.json")
    monkeypatch.setattr(MainWindow, "_refresh_process_map", lambda self: None)
    w1 = MainWindow()
    v = w1._collect_settings()
    v.update(theme="Dark", show_process=True)
    w1._apply_settings_values(v)  # persists via _save_settings

    w2 = MainWindow()
    w2._load_and_apply_settings()
    assert w2._theme_name == "Dark"
    assert w2.process_action.isChecked() is True
