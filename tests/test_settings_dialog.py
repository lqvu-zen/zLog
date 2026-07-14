"""Tests for the Settings dialog (view) and MainWindow apply round-trip."""

from __future__ import annotations

import pytest

_OPTS = dict(
    themes=["Light", "Dark"],
    time_modes=[("Absolute", "absolute"), ("Since start", "since_start"), ("Delta", "delta")],
    tail_options=[("Whole buffer", 0), ("Last 500", 500)],
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
        "wrap": True,
        "wrap_lines": 6,
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


def test_dialog_accepts_a_custom_buffer_limit(qapp):
    from zlog.ui.settings_dialog import SettingsDialog

    dlg = SettingsDialog({"max_rows": 250}, **_OPTS)
    dlg.max_spin.setValue(37500)  # any value, not just the old presets
    assert dlg.get_values()["max_rows"] == 37500


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
    assert window._max_rows == 10000
    assert window._font_delta == 2
    assert window.clear_on_start_action.isChecked() is True


def test_custom_buffer_limit_applies_and_persists(qapp, tmp_path, monkeypatch):
    from zlog.ui.main_window import MainWindow

    monkeypatch.setattr(MainWindow, "_settings_path", lambda self: tmp_path / "s.json")
    monkeypatch.setattr(MainWindow, "_refresh_process_map", lambda self: None)
    w1 = MainWindow()
    v = w1._collect_settings()
    v["max_rows"] = 12345  # an arbitrary, non-preset value
    w1._apply_settings_values(v)
    assert w1._max_rows == 12345
    assert w1._collect_settings()["max_rows"] == 12345

    w2 = MainWindow()
    w2._load_and_apply_settings()
    assert w2._max_rows == 12345  # custom value round-trips across relaunch


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


def _menu_walk_labels(menu):
    """All labels reachable by walking a menu (materialize lists to keep the
    PySide QAction/QMenu wrappers alive during traversal)."""
    labels = []
    for act in list(menu.actions()):
        sub = act.menu()
        if sub is not None:
            labels += _menu_walk_labels(sub)
        elif act.text():
            labels.append(act.text())
    return labels


def test_view_menu_decluttered_and_palette_parity(window):
    mb_actions = list(window.menuBar().actions())
    view = next(a.menu() for a in mb_actions if a.text() == "&View")
    view_labels = _menu_walk_labels(view)
    # Preference toggles were moved into the Settings dialog — not in the View menu.
    for gone in ("Show Process Names", "Collapse Repeated Lines", "Absolute", "Case sensitive"):
        assert gone not in view_labels, gone
    # Commands stay in the View menu.
    assert any("Clear F" in t for t in view_labels)  # Clear Filters
    assert any("Tag Summary" in t for t in view_labels)
    # Top-bar Settings entry after File/View, plus command-palette parity.
    assert "&Settings…" in [a.text() for a in mb_actions]
    cmds = [label for label, _ in window._all_commands()]
    assert "Settings" in cmds
    assert "Collapse Repeated Lines" in cmds
    assert "Absolute" in cmds


def test_wrap_setting_applies_and_grows_rows(qapp, tmp_path, monkeypatch):
    from PySide6.QtGui import QFontMetrics

    from zlog.ui.main_window import MainWindow

    monkeypatch.setattr(MainWindow, "_settings_path", lambda self: tmp_path / "s.json")
    monkeypatch.setattr(MainWindow, "_refresh_process_map", lambda self: None)
    w = MainWindow()
    line = QFontMetrics(w.table.font()).height()
    one = w.table.verticalHeader().defaultSectionSize()
    v = w._collect_settings()
    v.update(wrap=True, wrap_lines=5)
    w._apply_settings_values(v)
    assert w.log_delegate.wrap is True and w.log_delegate.wrap_lines == 5
    assert w.table.verticalHeader().defaultSectionSize() >= one + 4 * line
    # persists across relaunch
    w2 = MainWindow()
    w2._load_and_apply_settings()
    assert w2.log_delegate.wrap is True and w2.log_delegate.wrap_lines == 5
