"""Opening logs into tabs: reuse an idle tab, spawn a new one otherwise, label
by file name, and keep the streaming label. Offscreen Qt, no adb, no display."""

from __future__ import annotations

import pytest

from zlog.core.models import LogEntry


@pytest.fixture
def window(qapp, tmp_path, monkeypatch):
    from zlog.ui.main_window import MainWindow

    monkeypatch.setattr(MainWindow, "_settings_path", lambda self: tmp_path / "s.json")
    return MainWindow()


def _write_log(tmp_path, name):
    path = tmp_path / name
    path.write_text("06-30 12:00:00.000 1 1 I Tag: hello\n", encoding="utf-8")
    return str(path)


def test_open_reuses_idle_first_tab(window, tmp_path):
    path = _write_log(tmp_path, "a.log")
    window._open_log_in_tab(path)

    assert len(window._sessions) == 1  # empty tab reused, no new one
    assert window._active.title == "a.log"
    assert window.tab_bar.tabText(0) == "a.log"


def test_open_into_populated_tab_adds_tab(window, tmp_path):
    first = _write_log(tmp_path, "a.log")
    window._open_log_in_tab(first)  # tab 0 now holds a.log

    second = _write_log(tmp_path, "b.log")
    window._open_log_in_tab(second)

    assert len(window._sessions) == 2  # first tab kept, second opened alongside
    assert window.tab_bar.tabText(0) == "a.log"
    assert window.tab_bar.tabText(1) == "b.log"
    assert window._active_index == 1  # focus moves to the new tab


def test_new_tab_button_adds_tab(window):
    assert len(window._sessions) == 1
    window.new_tab_btn.click()
    assert len(window._sessions) == 2


def test_streaming_label_wins_over_title(window, tmp_path):
    sess = window._active
    sess.title = "a.log"

    class _FakeReader:
        pass

    sess.reader = _FakeReader()
    sess.serial = "emulator-5554"
    window._set_tab_label(sess)
    assert window.tab_bar.tabText(0) == "● emulator-5554"


def test_clear_drops_title_and_frees_tab(window, tmp_path):
    path = _write_log(tmp_path, "a.log")
    window._open_log_in_tab(path)
    assert window._active.title == "a.log"
    assert not window._tab_is_reusable(window._active)

    window._clear_active_view()
    assert window._active.title == ""
    assert window.tab_bar.tabText(0) == "Device"
    assert window._tab_is_reusable(window._active)


def test_tab_is_reusable_rules(window):
    sess = window._active
    assert window._tab_is_reusable(sess)  # fresh tab

    sess.model.append_entries([LogEntry("", "", "", "I", "T", "m")])
    assert not window._tab_is_reusable(sess)  # has rows

    sess.model.clear()
    sess.want_stream = True
    assert not window._tab_is_reusable(sess)  # intends to stream


def test_long_title_is_elided_with_tooltip(window, tmp_path):
    name = "a-very-long-capture-file-name.log"
    path = _write_log(tmp_path, name)
    window._open_log_in_tab(path)

    assert window.tab_bar.tabText(0).endswith("…")
    assert len(window.tab_bar.tabText(0)) <= 22
    assert window.tab_bar.tabToolTip(0) == name
