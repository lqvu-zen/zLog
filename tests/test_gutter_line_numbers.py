"""Gutter line numbers (see gutter-line-numbers.md)."""

from __future__ import annotations

import pytest

from zlog.core.models import LogEntry
from zlog.ui.log_delegate import LogItemDelegate
from zlog.ui.log_model import LogTableModel


class _FakeSrc:
    def __init__(self, n):
        self._n = n

    def rowCount(self):
        return self._n


def _fm():
    from PySide6.QtGui import QFont, QFontMetrics

    return QFontMetrics(QFont())


def test_gutter_width_zero_when_off(qapp):
    d = LogItemDelegate()
    assert d.line_numbers is False
    assert d._gutter_w(_FakeSrc(1000), _fm()) == 0


def test_gutter_width_grows_with_row_count(qapp):
    d = LogItemDelegate()
    d.line_numbers = True
    fm = _fm()
    few = d._gutter_w(_FakeSrc(9), fm)
    many = d._gutter_w(_FakeSrc(100000), fm)
    assert few > 0
    assert many > few  # more digits -> wider gutter


def test_gutter_shrinks_wrapped_message_width(qapp):
    # With the gutter on, a wrapped row's available message width is smaller, so a
    # borderline-length message wraps to a taller row than it would without it.
    from PySide6.QtCore import QRect
    from PySide6.QtWidgets import QStyleOptionViewItem

    model = LogTableModel()
    msg = "word " * 40
    model.append_entries([LogEntry("06-30 12:34:56.001", "1287", "1287", "I", "Tag", msg)])
    index = model.index(0, 0)

    d = LogItemDelegate()
    d.wrap = True
    opt = QStyleOptionViewItem()
    opt.rect = QRect(0, 0, 700, 20)

    d.line_numbers = False
    without = d.sizeHint(opt, index).height()
    d.line_numbers = True
    with_gutter = d.sizeHint(opt, index).height()
    assert with_gutter >= without


@pytest.fixture
def window(qapp, tmp_path, monkeypatch):
    from zlog.ui.main_window import MainWindow

    monkeypatch.setattr(MainWindow, "_settings_path", lambda self: tmp_path / "s.json")
    monkeypatch.setattr(MainWindow, "_refresh_process_map", lambda self: None)
    return MainWindow()


def test_line_numbers_persist_across_relaunch(qapp, tmp_path, monkeypatch):
    from zlog.ui.main_window import MainWindow

    monkeypatch.setattr(MainWindow, "_settings_path", lambda self: tmp_path / "s.json")
    monkeypatch.setattr(MainWindow, "_refresh_process_map", lambda self: None)
    w1 = MainWindow()
    v = w1._collect_settings()
    v["line_numbers"] = True
    w1._apply_settings_values(v)
    assert w1.log_delegate.line_numbers is True

    w2 = MainWindow()
    w2._load_and_apply_settings()
    assert w2.log_delegate.line_numbers is True
