"""Log font-family picker (see font-family-picker.md)."""

from __future__ import annotations

import pytest


@pytest.fixture
def window(qapp, tmp_path, monkeypatch):
    from zlog.ui.main_window import MainWindow

    monkeypatch.setattr(MainWindow, "_settings_path", lambda self: tmp_path / "s.json")
    monkeypatch.setattr(MainWindow, "_refresh_process_map", lambda self: None)
    return MainWindow()


def test_default_font_family_uses_the_builtin_chain(window):
    from zlog.ui.main_window import LOG_FONT_FAMILIES

    assert window._font_family == ""
    # No explicit pick: the built-in chain's first family leads.
    assert window.table.font().families()[0] == LOG_FONT_FAMILIES[0]


def test_set_font_family_leads_the_chain(window):
    from zlog.ui.main_window import LOG_FONT_FAMILIES

    window._set_font_family("Courier New")
    families = window.table.font().families()
    assert families[0] == "Courier New"
    # The built-in chain is still appended as a fallback so a missing pick degrades.
    assert families[1:] == LOG_FONT_FAMILIES
    assert window.table.font().fixedPitch() is True


def test_available_fonts_include_current_pick(window):
    window._set_font_family("Some Unlikely Custom Font")
    assert "Some Unlikely Custom Font" in window._available_log_fonts()


def test_font_family_persists_across_relaunch(qapp, tmp_path, monkeypatch):
    from zlog.ui.main_window import MainWindow

    monkeypatch.setattr(MainWindow, "_settings_path", lambda self: tmp_path / "s.json")
    monkeypatch.setattr(MainWindow, "_refresh_process_map", lambda self: None)
    w1 = MainWindow()
    v = w1._collect_settings()
    v["font_family"] = "Courier New"
    w1._apply_settings_values(v)
    assert w1._font_family == "Courier New"

    w2 = MainWindow()
    w2._load_and_apply_settings()
    assert w2._font_family == "Courier New"
    assert w2.table.font().families()[0] == "Courier New"
