"""Wrap re-fit on resize (see wrap-refit-on-resize.md).

A viewport width change re-flows wrapped rows, so the view must re-fit the
visible ones. These cover the two halves: the view emits `resized`, and the
window schedules a (debounced) fit from it — but only when wrap is on.
"""

from __future__ import annotations

import pytest

from zlog.core.models import LogEntry


@pytest.fixture
def window(qapp, tmp_path, monkeypatch):
    from zlog.ui.main_window import MainWindow

    path = tmp_path / "settings.json"
    monkeypatch.setattr(MainWindow, "_settings_path", lambda self: path)
    return MainWindow()


def test_view_emits_resized_on_resize(qapp):
    from zlog.ui.table_view import LogTableView

    view = LogTableView()
    view.resize(300, 200)
    view.show()  # a hidden widget doesn't deliver resizeEvent under offscreen
    qapp.processEvents()
    seen = []
    view.resized.connect(lambda: seen.append(True))
    view.resize(600, 240)
    qapp.processEvents()
    view.hide()
    assert seen  # resizeEvent fired the signal


def test_resize_schedules_fit_only_when_wrapping(window):
    # Wrap on: a resize arms the debounce timer that re-fits visible rows.
    window.log_delegate.wrap = True
    window._wrap_timer.stop()
    window.table.resized.emit()
    assert window._wrap_timer.isActive()

    # Wrap off: the same signal is a no-op (nothing to re-fit).
    window.log_delegate.wrap = False
    window._wrap_timer.stop()
    window.table.resized.emit()
    assert not window._wrap_timer.isActive()


def test_delegate_sizehint_grows_when_narrower(qapp):
    # The re-fit works because the delegate's wrapped sizeHint is width-sensitive:
    # a narrower cell wraps to more lines -> a taller row. (The end-to-end viewport
    # geometry isn't reliable under the offscreen platform, so assert the mechanism
    # the re-fit depends on directly.)
    from PySide6.QtCore import QRect
    from PySide6.QtWidgets import QStyleOptionViewItem

    from zlog.ui.log_delegate import LogItemDelegate
    from zlog.ui.log_model import LogTableModel

    model = LogTableModel()
    long_msg = (
        "Skipped 12 frames! The app may be doing too much work on its main thread, "
        "which is a common cause of jank and dropped frames overall, so keep heavy "
        "work off the UI thread wherever you possibly can to stay smooth."
    )
    model.append_entries(
        [LogEntry("06-30 12:34:56.110", "1287", "1287", "W", "Choreographer", long_msg)]
    )
    d = LogItemDelegate()
    d.wrap = True
    index = model.index(0, 0)

    opt = QStyleOptionViewItem()
    opt.rect = QRect(0, 0, 1000, 20)
    wide = d.sizeHint(opt, index).height()
    opt.rect = QRect(0, 0, 360, 20)
    narrow = d.sizeHint(opt, index).height()
    assert narrow > wide
