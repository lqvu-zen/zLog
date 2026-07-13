"""Headless round-trip tests for MainWindow settings persistence.

Guards the exact class of bug the declarative settings table was built to prevent:
a key that saves but doesn't restore (or vice versa). Runs under the offscreen Qt
platform (see conftest.py).
"""

from __future__ import annotations

import pytest

from zlog.core.devices import Device
from zlog.core.settings import DEFAULTS


@pytest.fixture
def window(qapp, tmp_path, monkeypatch):
    from zlog.ui.main_window import MainWindow

    path = tmp_path / "settings.json"
    monkeypatch.setattr(MainWindow, "_settings_path", lambda self: path)
    return MainWindow()


def test_specs_cover_exactly_defaults(window):
    keys = {key for key, _get, _set in window._settings_specs()}
    assert keys == set(DEFAULTS)


def test_settings_round_trip(qapp, tmp_path, monkeypatch):
    from zlog.ui.main_window import MainWindow

    path = tmp_path / "settings.json"
    monkeypatch.setattr(MainWindow, "_settings_path", lambda self: path)

    devices = [Device("AAA111", "device"), Device("BBB222", "device")]

    w1 = MainWindow()
    w1._populate_devices(devices)
    w1.device_box.setCurrentIndex(1)  # BBB222
    w1.apply_theme("Dark")
    w1._theme_name = "Dark"
    w1.follow_check.setChecked(False)
    w1.level_box.setCurrentIndex(4)  # E
    w1.regex_check.setChecked(True)
    w1.case_check.setChecked(True)
    w1.details_action.setChecked(False)
    w1.table.setColumnHidden(2, True)  # hide TID
    w1.clear_on_start_action.setChecked(True)
    w1.model.set_tag_color("Boom", "#ff0000")
    w1._save_settings()

    w2 = MainWindow()
    w2._populate_devices(devices)  # picker available before restore, as in real launch
    w2._load_and_apply_settings()

    assert w2._theme_name == "Dark"
    assert w2.follow_check.isChecked() is False
    assert w2.level_box.currentData() == "E"
    assert w2.regex_check.isChecked() is True
    assert w2.case_check.isChecked() is True
    assert w2.details_action.isChecked() is False
    assert w2.table.isColumnHidden(2) is True
    assert w2.clear_on_start_action.isChecked() is True
    assert w2.model.tag_colors().get("Boom", "").lower() == "#ff0000"
    assert w2.device_box.currentData() == "BBB222"


def test_missing_file_falls_back_to_defaults(window):
    # Fresh window, no settings file written yet: defaults applied, no crash.
    window._load_and_apply_settings()
    assert window._theme_name in ("Light", "Dark")
    assert window.follow_check.isChecked() == DEFAULTS["follow"]


def test_highlight_mode_shows_all_rows(window):
    from zlog.core.models import LogEntry

    window.model.append_entries(
        [LogEntry("t", "1", "1", "I", "T", "boom"), LogEntry("t", "1", "1", "I", "T", "quiet")]
    )
    # Filter mode hides non-matches...
    window.search.setText("boom")
    assert window.proxy.rowCount() == 1
    # ...Highlight mode shows everything while still matching.
    window.search_mode_box.setCurrentIndex(1)  # Highlight
    assert window.proxy.rowCount() == 2


def test_exclude_hides_lines(window):
    from zlog.core.models import LogEntry

    window.model.append_entries(
        [
            LogEntry("t", "1", "1", "I", "T", "keep me"),
            LogEntry("t", "1", "1", "I", "T", "spammy noise"),
        ]
    )
    window.query.setText("-spammy")  # exclude via the query bar
    assert window.proxy.rowCount() == 1


def test_match_navigation(window):
    from zlog.core.models import LogEntry

    window.model.append_entries(
        [
            LogEntry("t", "1", "1", "I", "T", "alpha"),
            LogEntry("t", "1", "1", "I", "T", "target one"),
            LogEntry("t", "1", "1", "I", "T", "beta"),
            LogEntry("t", "1", "1", "I", "T", "target two"),
        ]
    )
    window.search_mode_box.setCurrentIndex(1)  # highlight → all rows visible
    window.search.setText("target")
    assert window.match_label.text() == "2 matches"
    window._goto_match(1)
    assert window.table.currentIndex().row() == 1  # first match
    window._goto_match(1)
    assert window.table.currentIndex().row() == 3  # second match
    window._goto_match(1)
    assert window.table.currentIndex().row() == 1  # wraps to first


def test_showing_count_when_filtered(window):
    from zlog.core.models import LogEntry

    window.model.append_entries(
        [
            LogEntry("t", "1", "1", "I", "T", "keep"),
            LogEntry("t", "1", "1", "I", "T", "drop"),
            LogEntry("t", "1", "1", "I", "T", "keep too"),
        ]
    )
    window._update_counts()
    assert window.count_label.text().startswith("3 lines")
    window.search.setText("keep")  # filters to 2 of 3
    window._update_counts()
    assert window.count_label.text().startswith("Showing 2 of 3 lines")


def test_bookmark_toggle_and_navigation(window):
    from zlog.core.models import LogEntry

    window.model.append_entries([LogEntry("t", "1", "1", "I", "T", f"line {i}") for i in range(5)])
    # toggle via the action on the current selection
    window.table.setCurrentIndex(window.proxy.index(2, 0))
    window._toggle_bookmark()
    assert window.model.is_bookmarked(2) is True
    # add another and navigate between them
    window.model.toggle_bookmark(4)
    window._goto_bookmark(1)
    assert window.table.currentIndex().row() in (3, 4)  # next bookmark after row 2
    window._clear_bookmarks()
    assert window.model.bookmarked_rows() == []


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


def test_query_bar_drives_filters(window):
    from zlog.core.models import LogEntry

    window.model.append_entries(
        [
            LogEntry("t", "1", "1", "E", "Activity", "boom error"),
            LogEntry("t", "1", "1", "I", "Activity", "quiet info"),
            LogEntry("t", "1", "1", "E", "Other", "boom elsewhere"),
        ]
    )
    window.query.setText("level:E tag:Activity boom")
    assert window.proxy.rowCount() == 1  # E + tag Activity + "boom"
    # Clearing the query text drops tag/search, but level:E moved the visible Level
    # dropdown to E and that floor persists (the dropdown owns it now).
    window.query.clear()
    assert window.level_box.currentData() == "E"
    assert window.proxy.rowCount() == 2  # both E rows
    # Clear Filters is the full reset, including the level floor.
    window.clear_filters()
    assert window.proxy.rowCount() == 3


def test_mute_tag(window):
    from zlog.core.models import LogEntry

    window.model.append_entries(
        [
            LogEntry("t", "1", "1", "I", "GnssHal", "noise a"),
            LogEntry("t", "1", "1", "I", "Activity", "real one"),
        ]
    )
    assert window.proxy.rowCount() == 2
    window._mute_tag("GnssHal")
    assert "-GnssHal" in window.query.text()
    assert window.proxy.rowCount() == 1  # the GnssHal line is hidden
    window._mute_tag("GnssHal")  # idempotent
    assert window.query.text().count("-GnssHal") == 1


def test_query_history(window):
    window.query.setText("level:E boom")
    window._commit_query_history()
    window.query.setText("tag:Activity")
    window._commit_query_history()
    assert window._history[:2] == ["tag:Activity", "level:E boom"]
    assert window._history_model.stringList()[0] == "tag:Activity"


def test_level_multiselect(window):
    from zlog.core.models import LogEntry

    window.model.append_entries(
        [
            LogEntry("t", "1", "1", "V", "T", "v"),
            LogEntry("t", "1", "1", "W", "T", "w"),
            LogEntry("t", "1", "1", "E", "T", "e"),
            LogEntry("t", "1", "1", "I", "T", "i"),
        ]
    )
    window.query.setText("level:W,E")
    assert window.proxy.rowCount() == 2  # only W and E
    window.query.setText("level:E")  # floor -> E and above (just E here)
    assert window.proxy.rowCount() == 1


def test_log_buffers_persist(window):
    window._buffer_actions["radio"].setChecked(True)
    window._buffer_actions["events"].setChecked(True)
    keys = {k for k, _, _ in window._settings_specs()}
    assert "log_buffers" in keys
    got = next(g for k, g, _ in window._settings_specs() if k == "log_buffers")()
    assert set(got) == {"radio", "events"}


def test_clear_device_buffer_needs_device(window):
    # No device selected -> guidance message, no crash.
    window._clear_device_buffer()
    assert "device" in window.statusBar().currentMessage().lower()


def test_tail_count_setting(window):
    window._tail_actions[1000].setChecked(True)
    got = next(g for k, g, _ in window._settings_specs() if k == "tail_count")()
    assert got == 1000


def test_max_rows_setting_applies_to_model(window):
    window._max_rows_actions[50000].setChecked(True)
    keys = {k for k, _, _ in window._settings_specs()}
    assert "max_rows" in keys
    got = next(g for k, g, _ in window._settings_specs() if k == "max_rows")()
    assert got == 50000
    # the restore path also pushes the cap into the model
    setter = next(s for k, _, s in window._settings_specs() if k == "max_rows")
    setter(10000)
    assert window.model._max_rows == 10000


def test_clear_device_button_no_device(window):
    # The dedicated device-buffer button exists and, with no device selected,
    # routes through the guarded path (status message, no crash).
    assert hasattr(window, "clear_device_btn")
    window.clear_device_btn.click()
    assert "device" in window.statusBar().currentMessage().lower()


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


def test_clear_device_button_clears_view(window, monkeypatch):
    import zlog.ui.main_window as mw
    from zlog.core.models import LogEntry

    monkeypatch.setattr(mw, "clear_logcat", lambda *a, **k: True)
    monkeypatch.setattr(window, "_current_serial", lambda: "SER123")
    window.model.append_entries([LogEntry("t", "1", "2", "I", "T", "hi")])
    assert window.model.rowCount() == 1
    window.clear_device_btn.click()
    assert window.model.rowCount() == 0  # device clear also empties the view


def test_clear_device_button_keeps_view_on_failure(window, monkeypatch):
    import subprocess

    import zlog.ui.main_window as mw
    from zlog.core.models import LogEntry

    def boom(*a, **k):
        raise subprocess.CalledProcessError(1, "adb")

    monkeypatch.setattr(mw, "clear_logcat", boom)
    monkeypatch.setattr(window, "_current_serial", lambda: "SER123")
    window.model.append_entries([LogEntry("t", "1", "2", "I", "T", "hi")])
    window.clear_device_btn.click()
    assert window.model.rowCount() == 1  # failed clear must not wipe the view


def test_log_font_readable(window):
    from PySide6.QtGui import QFont

    f = window.table.font()
    assert f.styleHint() == QFont.Monospace
    assert f.pointSize() == 11  # BASE_FONT_PT at zero zoom
    window._zoom(2)
    assert window.table.font().pointSize() == 13  # zoom still shifts the base


def test_follow_stays_manual_and_never_yanks(window, qapp):
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
    qapp.processEvents()
    sb = window.table.verticalScrollBar()
    assert sb.maximum() > 0 and sb.value() == sb.maximum()  # tailing at the bottom

    # scroll up to read: Follow is a manual toggle, so it stays checked...
    sb.setValue(0)
    qapp.processEvents()
    assert window.follow_check.isChecked() is True
    # ...and incoming logs must NOT yank the viewport back down
    batch(50)
    qapp.processEvents()
    assert sb.value() == 0

    # scroll back to the bottom and tailing resumes on the next batch
    sb.setValue(sb.maximum())
    qapp.processEvents()
    batch(50)
    qapp.processEvents()
    assert sb.value() == sb.maximum()


def test_min_level_dropdown_floors_and_survives_query(window):
    from zlog.core.models import LogEntry

    window.model.append_entries(
        [
            LogEntry("t", "1", "2", "V", "T", "verbose"),
            LogEntry("t", "1", "2", "E", "T", "error"),
        ]
    )
    # pick E via the visible dropdown -> only E and above show
    window.level_box.setCurrentIndex(window.level_box.findData("E"))
    assert window.proxy.rowCount() == 1

    # a non-level query must NOT reset the floor back to V
    window.query.setText("error")
    assert window.level_box.currentData() == "E"
    assert window.proxy.rowCount() == 1

    # a level: token still drives the dropdown
    window.query.setText("level:V")
    assert window.level_box.currentData() == "V"

    # Clear Filters returns the floor to V and shows everything
    window.level_box.setCurrentIndex(window.level_box.findData("E"))
    window.clear_filters()
    assert window.level_box.currentData() == "V"
    assert window.proxy.rowCount() == 2


def test_pause_buffers_then_resume_flushes(window):
    from zlog.core.models import LogEntry

    def rows(n):
        return [LogEntry("t", "1", "2", "I", "T", f"l{i}") for i in range(n)]

    window._paused = True
    window.on_batch(rows(3))
    assert window.model.rowCount() == 0  # nothing shown while paused
    assert len(window._pause_buffer) == 3

    window._toggle_pause()  # resume
    assert window._paused is False
    assert window._pause_buffer == []
    assert window.model.rowCount() == 3  # buffered lines flushed in

    # after resume, live batches append normally again
    window.on_batch(rows(2))
    assert window.model.rowCount() == 5


def test_last_time_tracked_and_reconnect_resumes(window, monkeypatch):
    import zlog.ui.main_window as mw
    from zlog.core.devices import Device
    from zlog.core.models import LogEntry

    # on_batch remembers the newest real timestamp
    window.on_batch([LogEntry("06-30 12:00:00.000", "1", "2", "I", "T", "a")])
    window.on_batch([LogEntry("06-30 12:00:05.500", "1", "2", "I", "T", "b")])
    assert window._last_time == "06-30 12:00:05.500"

    # simulate a live session whose device dropped
    window._want_stream = True
    window._reconnect_serial = "SER1"
    calls = []
    monkeypatch.setattr(window, "_start_reader", lambda *a, **k: calls.append((a, k)))
    monkeypatch.setattr(mw, "list_devices", lambda *a, **k: [Device("SER1", "device")])

    window._try_reconnect()
    assert window._reconnect_timer.isActive() is False  # stopped once reconnected
    assert calls and calls[0][1].get("since_time") == "06-30 12:00:05.500"


def test_reconnect_waits_while_device_absent(window, monkeypatch):
    import zlog.ui.main_window as mw
    from zlog.core.devices import Device

    window._want_stream = True
    window._reconnect_serial = "SER1"
    called = []
    monkeypatch.setattr(window, "_start_reader", lambda *a, **k: called.append(1))
    monkeypatch.setattr(mw, "list_devices", lambda *a, **k: [Device("OTHER", "device")])
    window._try_reconnect()
    assert called == []  # target not back yet -> keep waiting, no restart


def test_stream_ended_ignored_after_user_stop(window):
    sess = window._active
    sess.want_stream = False
    window._on_stream_ended(sess)  # user stopped: must not start reconnect polling
    assert sess.reconnect_timer.isActive() is False


def test_open_recent_tracks_and_dedups(window, tmp_path):
    f = tmp_path / "cap.log"
    f.write_text("06-30 12:00:00.000 1 2 I Tag: hi\n", encoding="utf-8")
    window._load_log_file(str(f))
    assert window.model.rowCount() == 1
    assert window._recent[0] == str(f)
    # reopening moves it to the front without duplicating
    window._load_log_file(str(f))
    assert window._recent.count(str(f)) == 1


def test_open_missing_recent_is_forgotten(window, tmp_path):
    missing = str(tmp_path / "gone.log")
    window._recent = [missing]
    window._load_log_file(missing)  # OSError -> drop it
    assert missing not in window._recent


def test_reopen_last_loads_when_enabled(window, tmp_path):
    f = tmp_path / "s.log"
    f.write_text("06-30 12:00:00.000 1 2 I T: hi\n", encoding="utf-8")
    window._recent = [str(f)]
    window.reopen_last_action.setChecked(True)
    window._maybe_reopen_last()
    assert window.model.rowCount() == 1


def test_reopen_last_noop_when_disabled(window, tmp_path):
    f = tmp_path / "s.log"
    f.write_text("06-30 12:00:00.000 1 2 I T: hi\n", encoding="utf-8")
    window._recent = [str(f)]
    window.reopen_last_action.setChecked(False)
    window._maybe_reopen_last()
    assert window.model.rowCount() == 0


def test_session_save_and_restore(window, tmp_path):
    from zlog.core.models import LogEntry

    window.model.append_entries(
        [
            LogEntry("06-30 12:00:00.000", "1", "2", "I", "Act", "hi"),
            LogEntry("06-30 12:00:01.000", "1", "2", "E", "Boom", "crash"),
        ]
    )
    window.model.set_tag_color("Boom", "#ff0000")
    window.model.toggle_bookmark(1)
    window.query.setText("level:E")
    path = str(tmp_path / "s.zsession")
    window._write_session(path)

    w2 = type(window)()
    w2._read_session(path)
    assert w2.model.rowCount() == 2
    assert w2.query.text() == "level:E"
    assert w2.model.tag_colors() == {"Boom": "#ff0000"}
    assert w2.model.bookmarked_rows() == [1]
    assert w2.proxy.rowCount() == 1  # level:E restored and applied


def test_autosave_writes_and_rotates(window, tmp_path, monkeypatch):
    from zlog.core.models import LogEntry

    path = tmp_path / "autosave.log"
    monkeypatch.setattr(window, "_autosave_path", lambda: str(path))
    window._autosave_cap = 40  # tiny cap to force a rollover
    window.autosave_action.setChecked(True)

    def batch(msg):
        window._autosave([LogEntry("06-30 12:00:00.000", "1", "2", "I", "T", msg)])

    batch("first line long enough to pass the tiny cap")
    assert path.exists()
    batch("second line also long enough to roll over")
    assert (tmp_path / "autosave.1.log").exists()  # rotated the first write out


def test_autosave_off_writes_nothing(window, tmp_path, monkeypatch):
    from zlog.core.models import LogEntry

    path = tmp_path / "autosave.log"
    monkeypatch.setattr(window, "_autosave_path", lambda: str(path))
    window.autosave_action.setChecked(False)
    window._autosave([LogEntry("t", "1", "2", "I", "T", "x")])
    assert not path.exists()


def test_goto_severity_next_prev_and_wrap(window):
    from zlog.core.models import LogEntry

    window.model.append_entries(
        [
            LogEntry("t", "1", "2", "I", "T", "i0"),
            LogEntry("t", "1", "2", "W", "T", "w1"),
            LogEntry("t", "1", "2", "I", "T", "i2"),
            LogEntry("t", "1", "2", "E", "T", "e3"),
        ]
    )
    window._goto_severity(1)
    assert window.table.currentIndex().row() == 1  # first problem = W
    window._goto_severity(1)
    assert window.table.currentIndex().row() == 3  # next = E
    window._goto_severity(1)
    assert window.table.currentIndex().row() == 1  # wrap back to W
    window._goto_severity(-1)
    assert window.table.currentIndex().row() == 3  # previous wraps to E


def test_splitter_state_roundtrips(window):
    getter = next(g for k, g, _ in window._settings_specs() if k == "splitter_state")
    setter = next(s for k, _, s in window._settings_specs() if k == "splitter_state")
    saved = getter()
    assert isinstance(saved, str) and saved  # non-empty base64
    setter(saved)  # restores without error
    assert getter() == saved  # round-trips
    setter("")  # empty is a harmless no-op


def test_all_commands_includes_known_labels(window):
    labels = [label for label, _ in window._all_commands()]
    assert "Open Log" in labels
    assert "Tag Summary" in labels
    assert "Save Session" in labels


def test_watch_hits_and_clear(window):
    from zlog.core.models import LogEntry

    window._apply_watch("boom", announce=False)
    hits = window._watch_hits(
        [
            LogEntry("t", "1", "2", "I", "T", "all good"),
            LogEntry("t", "1", "2", "E", "Crash", "boom happened"),
        ]
    )
    assert [h.message for h in hits] == ["boom happened"]
    # clearing disables the watch
    window._apply_watch("", announce=False)
    assert window._watch is None
    assert window._watch_hits([LogEntry("t", "1", "2", "E", "T", "boom")]) == []


def test_new_window_is_independent(window):
    from zlog.ui.main_window import MainWindow

    before = len(MainWindow._open_windows)
    window._new_window()
    assert len(MainWindow._open_windows) == before + 1
    w2 = MainWindow._open_windows[-1]
    assert w2 is not window
    assert w2.model is not window.model  # fully independent stack
    w2.close()


def test_tabs_independent_and_concurrent(window):
    from zlog.core.models import LogEntry

    assert window.tab_bar.count() == 1 and len(window._sessions) == 1
    s0 = window._sessions[0]
    window._on_batch(s0, [LogEntry("t", "1", "2", "I", "A", "a")])

    window._new_tab()
    assert window.tab_bar.count() == 2 and window._active_index == 1
    s1 = window._sessions[1]
    assert s1.model is not s0.model  # independent stacks

    # a background tab keeps appending while another is active
    window._on_batch(s0, [LogEntry("t", "1", "2", "E", "A", "bg")])
    window._on_batch(s1, [LogEntry("t", "1", "2", "I", "B", "b")])
    assert s0.model.rowCount() == 2 and s1.model.rowCount() == 1
    assert window.model is s1.model  # active view is tab 1

    window.tab_bar.setCurrentIndex(0)
    assert window.model is s0.model  # switching swaps the visible model


def test_tab_query_is_per_tab(window):
    window.query.setText("level:E")
    window._new_tab()  # saves tab0's query, opens a fresh tab
    assert window.query.text() == ""  # new tab starts unfiltered
    window.tab_bar.setCurrentIndex(0)
    assert window.query.text() == "level:E"  # tab0's query restored


def test_cannot_close_last_tab(window):
    window._close_tab(0)
    assert window.tab_bar.count() == 1  # the last tab is kept


def test_saved_filters_sidebar(window):
    from zlog.core.presets import make_preset

    window._presets = [make_preset("Errors", min_level="E"), make_preset("Boom", search="boom")]
    window._rebuild_presets_menu()  # also refreshes the sidebar list
    assert window.presets_list.count() == 2

    window._on_preset_activated(window.presets_list.item(0))  # "Errors"
    assert window.level_box.currentData() == "E"  # preset sets the level floor

    window.presets_list.setCurrentRow(0)
    window._delete_selected_preset()
    assert window.presets_list.count() == 1
    assert [p["name"] for p in window._presets] == ["Boom"]


def test_add_query_token_filter(window):
    from zlog.core.query import parse_query

    window.query.setText("boom")
    window._add_query_token("level:E")
    assert "level:E" in window.query.text() and "boom" in window.query.text()

    window._add_query_token("level:W")  # same key replaces the previous level
    assert "level:E" not in window.query.text()
    assert parse_query(window.query.text()).level == "W"

    window._add_query_token("tag:Activity")
    assert parse_query(window.query.text()).tag == "Activity"


def test_add_query_token_quotes_spaces(window):
    from zlog.core.query import parse_query

    window.query.setText("")
    window._add_query_token("tag:My Tag")  # spaced value must round-trip
    assert parse_query(window.query.text()).tag == "My Tag"


def test_preset_resets_level_floor(window):
    from zlog.core.models import LogEntry
    from zlog.core.presets import make_preset

    window.model.append_entries(
        [
            LogEntry("t", "1", "1", "I", "T", "info"),
            LogEntry("t", "1", "1", "E", "T", "err"),
        ]
    )
    window._apply_preset(make_preset("Err", min_level="E"))
    assert window.proxy.rowCount() == 1  # only the E row
    # applying a show-all (V) preset must reset the floor and reveal both rows
    window._apply_preset(make_preset("All", min_level="V"))
    assert window.proxy.rowCount() == 2
