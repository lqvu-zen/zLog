"""Tests for the delegate's column-width budgeting (pure arithmetic, no paint)."""

from zlog.ui.log_delegate import (
    _MSG_MIN_FRAC,
    _PIDTID_W,
    _PROC_W,
    _TAG_W,
    _TIME_W,
    plan_tag_proc_widths,
)


def _message_fraction(usable, cw, show):
    tag_w, proc_w = plan_tag_proc_widths(usable, cw, show)
    gap = cw
    fixed = (_TIME_W * cw + gap) + (_PIDTID_W * cw + gap) + 3 * cw
    consumed = fixed + tag_w + gap + ((proc_w + gap) if show else 0)
    return (usable - consumed) / usable


def test_message_keeps_half_on_wide_rows():
    cw = 9
    for usable in (1000, 1400, 1920):
        for show in (False, True):
            frac = _message_fraction(usable, cw, show)
            # message keeps at least the guaranteed share (small float slack)
            assert frac >= _MSG_MIN_FRAC - 0.01, (usable, show, frac)


def test_flexible_columns_use_natural_width_when_there_is_room():
    cw = 9
    tag_w, proc_w = plan_tag_proc_widths(4000, cw, show=True)
    assert tag_w == _TAG_W * cw  # not shrunk on a very wide row
    assert proc_w == _PROC_W * cw


def test_flexible_columns_shrink_when_narrow():
    cw = 9
    tag_w, proc_w = plan_tag_proc_widths(1100, cw, show=True)
    assert tag_w < _TAG_W * cw  # squeezed to protect the message area
    assert proc_w < _PROC_W * cw
    assert tag_w >= 0 and proc_w >= 0
