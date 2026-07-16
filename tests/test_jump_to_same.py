"""Jump-to-same-tag/PID navigation over visible rows."""

from __future__ import annotations

import pytest

from zlog.core.models import LogEntry


@pytest.fixture
def window(qapp, tmp_path, monkeypatch):
    from zlog.ui.main_window import MainWindow

    monkeypatch.setattr(MainWindow, "_settings_path", lambda self: tmp_path / "s.json")
    return MainWindow()


def _seed(window):
    window.model.append_entries(
        [
            LogEntry("06-30 12:00:00.000", "100", "200", "I", "TagA", "a0"),
            LogEntry("06-30 12:00:01.000", "200", "201", "I", "TagB", "b0"),
            LogEntry("06-30 12:00:02.000", "100", "200", "I", "TagA", "a1"),
        ]
    )


def test_next_same_tag_skips_other_tags(window):
    _seed(window)
    window.table.setCurrentIndex(window.proxy.index(0, 0))
    window._goto_same("tag", 1)
    assert window.table.currentIndex().row() == 2  # skipped TagB at row 1


def test_next_same_tag_wraps(window):
    _seed(window)
    window.table.setCurrentIndex(window.proxy.index(2, 0))
    window._goto_same("tag", 1)
    assert window.table.currentIndex().row() == 0  # wrapped back to the first TagA


def test_prev_same_pid(window):
    _seed(window)
    window.table.setCurrentIndex(window.proxy.index(2, 0))
    window._goto_same("pid", -1)
    assert window.table.currentIndex().row() == 0  # PID 100 at rows 0 and 2


def test_no_selection_is_a_noop(window):
    _seed(window)
    window.table.clearSelection()
    window.table.setCurrentIndex(window.proxy.index(-1, -1))
    window._goto_same("tag", 1)  # no valid current row -> no crash
    assert window.table.currentIndex().row() == -1


def test_empty_field_is_a_noop(window):
    # A banner/unparsed line has an empty tag; jumping by tag does nothing.
    window.model.append_entries([LogEntry("", "", "", "", "", "--- banner")])
    window.table.setCurrentIndex(window.proxy.index(0, 0))
    window._goto_same("tag", 1)
    assert window.table.currentIndex().row() == 0
