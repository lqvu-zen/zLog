"""Presentation toggles: font zoom (Ctrl+=/-/0, Ctrl+wheel) and the base
monospace log font.

Split out of test_main_window_settings.py (see docs/plans/split-settings-tests.md).
Density modes, word-wrap, and gutter line numbers already have their own files
(test_density.py, test_wrap_refit.py, test_gutter_line_numbers.py) — zoom and
the base font were the only "presentation toggle" tests still living here.
"""

from __future__ import annotations

import pytest


@pytest.fixture
def window(qapp, tmp_path, monkeypatch):
    from zlog.ui.main_window import MainWindow

    path = tmp_path / "settings.json"
    monkeypatch.setattr(MainWindow, "_settings_path", lambda self: path)
    return MainWindow()


def test_font_zoom(window):
    base = window.table.font().pointSize()
    window._zoom(2)
    assert window.table.font().pointSize() == base + 2
    assert window.detail.font().pointSize() == base + 2
    window._reset_zoom()
    assert window.table.font().pointSize() == base
    # persists through the settings spec
    window._zoom(3)
    window._save_settings()
    from zlog.ui.main_window import MainWindow

    w2 = MainWindow()
    w2._load_and_apply_settings()
    assert w2._font_delta == 3


def _wheel(dy, ctrl):
    from PySide6.QtCore import QPoint, QPointF, Qt
    from PySide6.QtGui import QWheelEvent

    mods = Qt.ControlModifier if ctrl else Qt.NoModifier
    return QWheelEvent(
        QPointF(5, 5),
        QPointF(5, 5),
        QPoint(0, 0),
        QPoint(0, dy),
        Qt.NoButton,
        mods,
        Qt.ScrollUpdate,
        False,
    )


def test_ctrl_wheel_zooms(window):
    before = window._font_delta
    assert window.eventFilter(window.table.viewport(), _wheel(120, ctrl=True)) is True
    assert window._font_delta == before + 1
    # and down over the detail pane
    assert window.eventFilter(window.detail.viewport(), _wheel(-120, ctrl=True)) is True
    assert window._font_delta == before


def test_plain_wheel_not_consumed(window):
    before = window._font_delta
    assert window.eventFilter(window.table.viewport(), _wheel(120, ctrl=False)) is False
    assert window._font_delta == before


def test_log_font_readable(window):
    from PySide6.QtGui import QFont

    f = window.table.font()
    assert f.styleHint() == QFont.Monospace
    assert f.pointSize() == 11  # BASE_FONT_PT at zero zoom
    window._zoom(2)
    assert window.table.font().pointSize() == 13  # zoom still shifts the base
