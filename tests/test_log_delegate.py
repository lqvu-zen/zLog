"""Tests for the delegate's column-width budgeting (pure arithmetic, no paint)."""

from zlog.ui.log_delegate import (
    _MSG_MIN_FRAC,
    _PROC_W,
    _TAG_W,
    plan_tag_proc_widths,
)


def _fixed_px(cw, time_chars=18, pid_chars=9):
    # Time + PID (content-sized) + Level chip, each with its trailing gap.
    return (time_chars * cw + cw) + (pid_chars * cw + cw) + 3 * cw


def _message_fraction(usable, cw, show):
    fixed = _fixed_px(cw)
    tag_w, proc_w = plan_tag_proc_widths(usable, cw, show, fixed)
    consumed = fixed + tag_w + cw + ((proc_w + cw) if show else 0)
    return (usable - consumed) / usable


def test_message_keeps_half_on_wide_rows():
    cw = 9
    for usable in (1000, 1400, 1920):
        for show in (False, True):
            frac = _message_fraction(usable, cw, show)
            assert frac >= _MSG_MIN_FRAC - 0.01, (usable, show, frac)


def test_flexible_columns_use_natural_width_when_there_is_room():
    cw = 9
    tag_w, proc_w = plan_tag_proc_widths(4000, cw, show=True, fixed_px=_fixed_px(cw))
    assert tag_w == _TAG_W * cw  # not shrunk on a very wide row
    assert proc_w == _PROC_W * cw


def test_flexible_columns_shrink_when_narrow():
    cw = 9
    tag_w, proc_w = plan_tag_proc_widths(1100, cw, show=True, fixed_px=_fixed_px(cw))
    assert tag_w < _TAG_W * cw  # squeezed to protect the message area
    assert proc_w < _PROC_W * cw
    assert tag_w >= 0 and proc_w >= 0


def test_sizehint_wraps_to_full_message(qapp):
    from PySide6.QtCore import QRect
    from PySide6.QtGui import QFont
    from PySide6.QtWidgets import QStyleOptionViewItem

    from zlog.core.models import LogEntry
    from zlog.ui.log_delegate import LogItemDelegate
    from zlog.ui.log_model import LogFilterProxy, LogTableModel

    model = LogTableModel()
    proxy = LogFilterProxy()
    proxy.setSourceModel(model)
    model.append_entries(
        [
            LogEntry("t", "1", "1", "I", "T", "short"),
            LogEntry("t", "1", "1", "I", "T", "word " * 200),  # very long
        ]
    )
    d = LogItemDelegate()
    opt = QStyleOptionViewItem()
    opt.font = QFont()
    opt.rect = QRect(0, 0, 320, 20)  # a fixed, narrow column width

    # wrap off: every row is a single line
    h0 = d.sizeHint(opt, proxy.index(0, 0)).height()
    h1 = d.sizeHint(opt, proxy.index(1, 0)).height()
    assert h0 == h1

    d.wrap = True
    short_h = d.sizeHint(opt, proxy.index(0, 0)).height()
    long_h = d.sizeHint(opt, proxy.index(1, 0)).height()
    assert long_h > short_h  # the long message wraps to more lines -> taller row
