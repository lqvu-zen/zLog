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
    assert window.tab_bar.tabText(0) == "a.log (1)"


def test_open_into_populated_tab_adds_tab(window, tmp_path):
    first = _write_log(tmp_path, "a.log")
    window._open_log_in_tab(first)  # tab 0 now holds a.log

    second = _write_log(tmp_path, "b.log")
    window._open_log_in_tab(second)

    assert len(window._sessions) == 2  # first tab kept, second opened alongside
    assert window.tab_bar.tabText(0) == "a.log (1)"
    assert window.tab_bar.tabText(1) == "b.log (1)"
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

    text = window.tab_bar.tabText(0)
    assert "…" in text  # the long name is elided...
    assert text.endswith("(1)")  # ...but the count survives
    assert name in window.tab_bar.tabToolTip(0)  # tooltip is never elided


# --- tab-bar polish: state, reordering, close guard ------------------------
def test_streaming_tab_shows_count(window, tmp_path):
    from zlog.core.models import LogEntry

    sess = window._active
    sess.serial = "emulator-5554"

    class _FakeReader:
        pass

    sess.reader = _FakeReader()
    sess.model.append_entries([LogEntry("", "", "", "I", "T", f"m{i}") for i in range(1500)])
    window._set_tab_label(sess)
    assert window.tab_bar.tabText(0) == "● emulator-5554 (1.5k)"


def test_paused_tab_shows_pause_marker(window):
    class _FakeReader:
        pass

    sess = window._active
    sess.serial = "dev"
    sess.reader = _FakeReader()
    sess.paused = True
    window._set_tab_label(sess)
    assert window.tab_bar.tabText(0).startswith("⏸")


def test_disconnected_tab_shows_warning_marker(window):
    sess = window._active
    sess.serial = "dev"
    sess.want_stream = True  # intending to stream, but no reader = dropped
    window._set_tab_label(sess)
    assert window.tab_bar.tabText(0).startswith("⚠")


def test_tooltip_spells_out_state(window):
    class _FakeReader:
        pass

    sess = window._active
    sess.serial = "dev"
    sess.reader = _FakeReader()
    window._set_tab_label(sess)
    assert "streaming" in window.tab_bar.tabToolTip(0)


def test_reorder_keeps_sessions_and_active_aligned(window, tmp_path):
    """The risky one: the bar's order and _sessions must not diverge, or a tab
    would show another tab's log."""
    window._open_log_in_tab(_write_log(tmp_path, "a.log"))
    window._open_log_in_tab(_write_log(tmp_path, "b.log"))
    first, second = window._sessions[0], window._sessions[1]
    assert window._active is second

    window._on_tab_moved(0, 1)  # drag tab 0 past tab 1

    assert window._sessions == [second, first]  # list follows the bar
    assert window._active is second  # the same session stays active
    assert window._active_index == 0  # ...at its new index


def test_reorder_ignores_out_of_range(window):
    before = list(window._sessions)
    window._on_tab_moved(0, 5)
    window._on_tab_moved(3, 0)
    window._on_tab_moved(0, 0)
    assert window._sessions == before


def test_closing_a_streaming_tab_asks_first(window, monkeypatch):
    class _FakeReader:
        def __init__(self):
            self.stopped = False

        def stop(self):
            self.stopped = True

    window._new_tab()
    sess = window._sessions[1]
    reader = _FakeReader()
    sess.reader = reader

    monkeypatch.setattr(window, "_confirm_close_streaming", lambda s: False)  # decline
    window._close_tab(1)
    assert len(window._sessions) == 2  # tab kept
    assert sess.reader is reader and not reader.stopped  # and still capturing

    monkeypatch.setattr(window, "_confirm_close_streaming", lambda s: True)  # accept
    window._close_tab(1)
    assert len(window._sessions) == 1
    assert reader.stopped


def test_closing_an_idle_tab_does_not_ask(window, monkeypatch):
    """Prompting for a tab that isn't capturing would just be noise."""
    asked = {"n": 0}
    monkeypatch.setattr(
        window, "_confirm_close_streaming", lambda s: asked.__setitem__("n", asked["n"] + 1) or True
    )
    window._new_tab()
    window._close_tab(1)
    assert asked["n"] == 0
    assert len(window._sessions) == 1
