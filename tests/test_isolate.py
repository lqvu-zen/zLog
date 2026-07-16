"""The "Isolate" toggle: narrow to a row's pid+tag, then restore the prior query."""

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
            LogEntry("06-30 12:00:00.000", "100", "200", "I", "Activity", "a"),
            LogEntry("06-30 12:00:01.000", "200", "201", "I", "Other", "b"),
        ]
    )


def test_isolate_narrows_to_pid_and_tag(window):
    _seed(window)
    window.table.setCurrentIndex(window.proxy.index(0, 0))
    window._toggle_isolate(window._current_entry())
    assert window.query.text() == "pid:100 tag:Activity"


def test_isolate_toggle_restores_prior_query(window):
    _seed(window)
    window.query.setText("level:V")  # a prior query that doesn't hide either row
    window._apply_query()
    window.table.setCurrentIndex(window.proxy.index(0, 0))
    window._toggle_isolate(window._current_entry())
    assert window.query.text() == "pid:100 tag:Activity"
    window._toggle_isolate(window._current_entry())
    assert window.query.text() == "level:V"


def test_isolate_no_selection_is_a_noop(window):
    _seed(window)
    window._toggle_isolate(window._current_entry())
    assert window.query.text() == ""


def test_manual_edit_after_isolate_clears_restore_state(window):
    _seed(window)
    window.table.setCurrentIndex(window.proxy.index(0, 0))
    window._toggle_isolate(window._current_entry())
    assert window._isolate_prev_query is not None
    # A real keystroke (not a programmatic _set_query_text) reaches
    # _schedule_query_apply and should drop the saved "restore" state.
    window.query.setText("pid:100 tag:Activity extra")
    assert window._isolate_prev_query is None


def test_clear_filters_drops_isolate_state(window):
    _seed(window)
    window.table.setCurrentIndex(window.proxy.index(0, 0))
    window._toggle_isolate(window._current_entry())
    window.clear_filters()
    assert window._isolate_prev_query is None
    assert window.query.text() == ""
