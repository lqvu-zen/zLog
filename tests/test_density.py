"""Row-density presets (see density-modes.md)."""

from __future__ import annotations

import pytest

from zlog.core.density import DENSITY_NAMES, DENSITY_PAD, density_pad


def test_density_pad_known_presets():
    assert density_pad("compact") < density_pad("default") < density_pad("comfortable")


def test_density_pad_unknown_falls_back_to_default():
    assert density_pad("nonsense") == DENSITY_PAD["default"]


def test_density_names_cover_the_pad_map():
    assert set(DENSITY_NAMES) == set(DENSITY_PAD)


@pytest.fixture
def window(qapp, tmp_path, monkeypatch):
    from zlog.ui.main_window import MainWindow

    monkeypatch.setattr(MainWindow, "_settings_path", lambda self: tmp_path / "s.json")
    monkeypatch.setattr(MainWindow, "_refresh_process_map", lambda self: None)
    return MainWindow()


def test_set_density_drives_delegate_and_row_height(window):
    from PySide6.QtWidgets import QHeaderView

    window._set_density("comfortable")
    assert window.log_delegate.row_pad == DENSITY_PAD["comfortable"]
    vh = window.table.verticalHeader()
    tall = vh.defaultSectionSize()

    window._set_density("compact")
    assert window.log_delegate.row_pad == DENSITY_PAD["compact"]
    short = vh.defaultSectionSize()

    assert short < tall  # tighter density -> shorter rows
    # rows stay Fixed (never ResizeToContents) regardless of density
    assert vh.sectionResizeMode(0) == QHeaderView.Fixed


def test_density_persists_across_relaunch(qapp, tmp_path, monkeypatch):
    from zlog.ui.main_window import MainWindow

    monkeypatch.setattr(MainWindow, "_settings_path", lambda self: tmp_path / "s.json")
    monkeypatch.setattr(MainWindow, "_refresh_process_map", lambda self: None)
    w1 = MainWindow()
    v = w1._collect_settings()
    v["density"] = "compact"
    w1._apply_settings_values(v)
    assert w1._density == "compact"

    w2 = MainWindow()
    w2._load_and_apply_settings()
    assert w2._density == "compact"
    assert w2.log_delegate.row_pad == DENSITY_PAD["compact"]
