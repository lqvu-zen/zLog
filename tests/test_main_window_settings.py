"""Headless round-trip tests for MainWindow settings persistence.

Guards the exact class of bug the declarative settings table was built to prevent:
a key that saves but doesn't restore (or vice versa). Runs under the offscreen Qt
platform (see conftest.py).
"""

from __future__ import annotations

import pytest

from zlog.core.devices import Device
from zlog.core.settings import DEFAULTS


@pytest.fixture
def window(qapp, tmp_path, monkeypatch):
    from zlog.ui.main_window import MainWindow

    path = tmp_path / "settings.json"
    monkeypatch.setattr(MainWindow, "_settings_path", lambda self: path)
    return MainWindow()


def test_specs_cover_exactly_defaults(window):
    keys = {key for key, _get, _set in window._settings_specs()}
    assert keys == set(DEFAULTS)


def test_settings_round_trip(qapp, tmp_path, monkeypatch):
    from zlog.ui.main_window import MainWindow

    path = tmp_path / "settings.json"
    monkeypatch.setattr(MainWindow, "_settings_path", lambda self: path)

    devices = [Device("AAA111", "device"), Device("BBB222", "device")]

    w1 = MainWindow()
    w1._populate_devices(devices)
    w1.device_box.setCurrentIndex(1)  # BBB222
    w1.apply_theme("Dark")
    w1._theme_name = "Dark"
    w1.follow_check.setChecked(False)
    w1.level_box.setCurrentIndex(4)  # E
    w1.regex_check.setChecked(True)
    w1.case_check.setChecked(True)
    w1.details_action.setChecked(False)
    w1.table.setColumnHidden(2, True)  # hide TID
    w1.clear_on_start_action.setChecked(True)
    w1.model.set_tag_color("Boom", "#ff0000")
    w1._save_settings()

    w2 = MainWindow()
    w2._populate_devices(devices)  # picker available before restore, as in real launch
    w2._load_and_apply_settings()

    assert w2._theme_name == "Dark"
    assert w2.follow_check.isChecked() is False
    assert w2.level_box.currentData() == "E"
    assert w2.regex_check.isChecked() is True
    assert w2.case_check.isChecked() is True
    assert w2.details_action.isChecked() is False
    assert w2.table.isColumnHidden(2) is True
    assert w2.clear_on_start_action.isChecked() is True
    assert w2.model.tag_colors().get("Boom", "").lower() == "#ff0000"
    assert w2.device_box.currentData() == "BBB222"


def test_missing_file_falls_back_to_defaults(window):
    # Fresh window, no settings file written yet: defaults applied, no crash.
    window._load_and_apply_settings()
    assert window._theme_name in ("Light", "Dark")
    assert window.follow_check.isChecked() == DEFAULTS["follow"]


def test_highlight_mode_shows_all_rows(window):
    from zlog.core.models import LogEntry

    window.model.append_entries(
        [LogEntry("t", "1", "1", "I", "T", "boom"), LogEntry("t", "1", "1", "I", "T", "quiet")]
    )
    # Filter mode hides non-matches...
    window.search.setText("boom")
    assert window.proxy.rowCount() == 1
    # ...Highlight mode shows everything while still matching.
    window.search_mode_box.setCurrentIndex(1)  # Highlight
    assert window.proxy.rowCount() == 2
