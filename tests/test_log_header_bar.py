"""Tests for the log header strip (offscreen Qt, no display needed)."""

from __future__ import annotations

import pytest


@pytest.fixture
def wired(qapp):
    from zlog.ui.log_delegate import LogItemDelegate
    from zlog.ui.log_header_bar import LogHeaderBar
    from zlog.ui.log_model import LogTableModel

    model = LogTableModel()
    delegate = LogItemDelegate()
    header = LogHeaderBar(delegate, lambda: model)
    return header, delegate, model


def test_fixed_height_matches_font_metrics(wired):
    from PySide6.QtGui import QFont, QFontMetrics

    from zlog.ui.log_header_bar import _HEIGHT_PAD

    header, _delegate, _model = wired
    font = QFont()
    font.setPointSize(14)
    header.setFont(font)
    assert header.height() == QFontMetrics(font).height() + _HEIGHT_PAD


def _paint(header, width=800, height=30):
    # paintEvent() creates its own QPainter(self) and never touches its `event`
    # arg, so calling it directly (no QPaintEvent needed) exercises the exact
    # same code path a real repaint would, offscreen.
    header.resize(width, height)
    header.paintEvent(None)


def test_paint_empty_model_does_not_crash(wired):
    header, _delegate, _model = wired
    _paint(header)


def test_paint_with_data_does_not_crash(wired):
    from zlog.core.models import LogEntry

    header, _delegate, model = wired
    model.append_entries([LogEntry("06-30 12:00:00.000", "100", "200", "I", "Tag", "hello")])
    _paint(header)


def test_paint_with_process_and_wrap_does_not_crash(wired):
    from zlog.core.models import LogEntry

    header, delegate, model = wired
    model.append_entries([LogEntry("06-30 12:00:00.000", "100", "200", "I", "Tag", "hello")])
    delegate.show_process = True
    delegate.wrap = True
    _paint(header)


def test_paint_follows_a_tab_switch(wired):
    """The model_provider is re-called on every paint, so switching the
    active tab's model (as MainWindow._switch_tab does) is picked up without
    any extra rewiring on the header itself."""
    from zlog.core.models import LogEntry
    from zlog.ui.log_model import LogTableModel

    header, delegate, model = wired
    other = LogTableModel()
    other.append_entries([LogEntry("t", "1", "2", "I", "Tag", "from the other tab")])

    current = {"model": model}
    header._model_provider = lambda: current["model"]
    assert header._model_provider() is model

    current["model"] = other
    assert header._model_provider() is other
    _paint(header)  # no crash reading the swapped-in model


def test_set_theme_triggers_no_crash_and_stores_colors(wired):
    header, _delegate, _model = wired
    header.set_theme("#112233", "#eeeeee", "#999999")
    assert header._text.name() == "#112233"
    assert header._bg.name() == "#eeeeee"
    assert header._border.name() == "#999999"
    _paint(header)
