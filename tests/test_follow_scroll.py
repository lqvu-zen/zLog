"""Follow (tail) / auto-scroll behavior.

Split out of test_main_window_settings.py (see docs/plans/split-settings-tests.md):
this is the subject that produced a real order-dependent flake
(fix-follow-scroll-flake.md), and grouping it made the two-pass-plus-deferred
-re-pin behavior reason-about-able in one place.
"""

from __future__ import annotations

import pytest


@pytest.fixture
def window(qapp, tmp_path, monkeypatch):
    from zlog.ui.main_window import MainWindow

    path = tmp_path / "settings.json"
    monkeypatch.setattr(MainWindow, "_settings_path", lambda self: path)
    return MainWindow()


def test_follow_stays_manual_and_never_yanks(window, qapp):
    from PySide6.QtTest import QTest

    from zlog.core.models import LogEntry

    window.resize(1100, 700)
    window.show()
    qapp.processEvents()

    def batch(n):
        window.on_batch(
            [
                LogEntry(f"06-30 12:00:{i % 60:02d}.000", "1", "2", "I", "T", f"l{i}")
                for i in range(n)
            ]
        )

    window.follow_check.setChecked(True)
    for _ in range(20):
        batch(50)
    QTest.qWait(150)  # the follow scroll is coalesced onto a short timer
    sb = window.table.verticalScrollBar()
    assert sb.maximum() > 0 and sb.value() == sb.maximum()  # tailing at the bottom

    # scroll up to read: Follow is a manual toggle, so it stays checked...
    sb.setValue(0)
    qapp.processEvents()
    assert window.follow_check.isChecked() is True
    # ...and incoming logs must NOT yank the viewport back down
    batch(50)
    QTest.qWait(150)
    assert sb.value() == 0

    # scroll back to the bottom and tailing resumes on the next batch
    sb.setValue(sb.maximum())
    qapp.processEvents()
    batch(50)
    QTest.qWait(150)
    assert sb.value() == sb.maximum()


def test_follow_pauses_while_a_row_is_selected(window, qapp):
    from PySide6.QtTest import QTest

    from zlog.core.models import LogEntry

    window.resize(1100, 700)
    window.show()
    qapp.processEvents()

    def batch(n):
        window.on_batch(
            [
                LogEntry(f"06-30 12:00:{i % 60:02d}.000", "1", "2", "I", "T", f"l{i}")
                for i in range(n)
            ]
        )

    window.follow_check.setChecked(True)
    for _ in range(20):
        batch(50)
    QTest.qWait(150)
    sb = window.table.verticalScrollBar()
    assert sb.value() >= sb.maximum() - 4  # tailing at the bottom (same tolerance as the gate)

    # select a row while still at the bottom (a click doesn't move the scrollbar)
    window.table.selectRow(window.proxy.rowCount() - 1)
    assert window.table.selectionModel().hasSelection()
    stuck_at = sb.value()

    # the next batch must not yank the view away from the selected row
    batch(50)
    QTest.qWait(150)
    assert sb.value() == stuck_at

    # clearing the selection and returning to the bottom resumes tailing
    window.table.clearSelection()
    sb.setValue(sb.maximum())
    qapp.processEvents()
    batch(50)
    QTest.qWait(150)
    assert sb.value() >= sb.maximum() - 4


def test_follow_resumes_on_scroll_to_bottom_without_manually_deselecting(window, qapp):
    """Regression: scrolling back to the newest line should let go of a stale
    selection itself — the user shouldn't have to deselect by hand for Follow
    to resume."""
    from PySide6.QtTest import QTest

    from zlog.core.models import LogEntry

    window.resize(1100, 700)
    window.show()
    qapp.processEvents()

    def batch(n):
        window.on_batch(
            [
                LogEntry(f"06-30 12:00:{i % 60:02d}.000", "1", "2", "I", "T", f"l{i}")
                for i in range(n)
            ]
        )

    window.follow_check.setChecked(True)
    for _ in range(20):
        batch(50)
    QTest.qWait(150)
    sb = window.table.verticalScrollBar()

    # select the last row while it's already fully visible (no scroll induced —
    # the case that broke the naive "consume on next scroll" suppression)
    window.table.selectRow(window.proxy.rowCount() - 1)
    assert window.table.selectionModel().hasSelection()

    batch(50)  # must not yank while selected
    QTest.qWait(150)

    # user scrolls back to the bottom themselves, without touching the selection
    sb.setValue(sb.maximum())
    qapp.processEvents()
    assert not window.table.selectionModel().hasSelection()  # auto-cleared

    batch(50)
    QTest.qWait(150)
    assert sb.value() >= sb.maximum() - 4  # tailing resumed
