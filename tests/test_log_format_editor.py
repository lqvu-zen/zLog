"""User-defined log formats through the window: detection on open, the level
gate actually working on a custom format, persistence, and the dialog wiring.

See docs/plans/custom-log-format-editor.md.
"""

from __future__ import annotations

import pytest

from zlog.core.logformat import LogFormat


@pytest.fixture
def window(qapp, tmp_path, monkeypatch):
    from zlog.ui.main_window import MainWindow

    monkeypatch.setattr(MainWindow, "_settings_path", lambda self: tmp_path / "s.json")
    return MainWindow()


_CUSTOM = LogFormat(
    name="MyProject",
    pattern=r"^(?P<time>\d+) \[(?P<level>\w+)\] (?P<tag>\w+): (?P<message>.*)$",
    level_aliases={"ERROR": "E", "WARN": "W", "INFO": "I"},
)


def _write(tmp_path, name, text):
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return str(path)


# --- default path: no user formats configured -------------------------------


def test_no_user_formats_behaves_as_before(window, tmp_path):
    path = _write(tmp_path, "cap.log", "06-30 12:00:00.000 1 2 I Tag: hi\n")
    window._load_log_file(path)
    assert window.model.rowCount() == 1
    assert window.model.entry_at(0).level == "I"
    # A built-in winner (e.g. threadtime) is not announced — only a
    # user-defined format earns the note (see _format_note); naming
    # "threadtime" on every ordinary open would be pure noise.
    assert "Format:" not in window.statusBar().currentMessage()
    assert window._active.format == "threadtime"  # still remembered internally


# --- auto-detect on open -----------------------------------------------------


def test_open_detects_a_configured_custom_format(window, tmp_path):
    window._log_formats = [_CUSTOM]
    path = _write(
        tmp_path,
        "myproject.log",
        "1000 [ERROR] Boom: it broke\n1001 [INFO] Net: fine\n",
    )
    window._load_log_file(path)
    assert window.model.rowCount() == 2
    assert window.model.entry_at(0).level == "E"
    assert window.model.entry_at(0).tag == "Boom"
    assert "Format: MyProject" in window.statusBar().currentMessage()
    assert window._active.format == "MyProject"


def test_the_level_gate_actually_works_on_a_detected_custom_format(window, tmp_path):
    # This is the whole point of the feature (see the plan's "Why"): the
    # Level dropdown must filter a custom format exactly like it filters logcat.
    window._log_formats = [_CUSTOM]
    path = _write(
        tmp_path,
        "myproject.log",
        "1000 [ERROR] Boom: it broke\n1001 [INFO] Net: fine\n",
    )
    window._load_log_file(path)
    window.proxy.set_min_level("E")
    assert window.proxy.rowCount() == 1  # only the ERROR line


def test_no_confident_match_falls_back_to_builtins_only(window, tmp_path):
    window._log_formats = [_CUSTOM]
    path = _write(tmp_path, "cap.log", "06-30 12:00:00.000 1 2 I Tag: hi\n")
    window._load_log_file(path)
    # A real logcat line doesn't match _CUSTOM's pattern at all, so detection
    # has exactly one candidate (threadtime) and picks it, not "no format".
    assert window.model.entry_at(0).level == "I"
    assert window._active.format == "threadtime"


def test_two_tabs_each_keep_their_own_format_concurrently(window, tmp_path):
    # The whole reason format choice is per-tab (decision 1) rather than
    # global: one tab on logcat, another on a custom format, both correct at
    # the same time.
    window._log_formats = [_CUSTOM]
    logcat_path = _write(tmp_path, "cap.log", "06-30 12:00:00.000 1 2 I Tag: hi\n")
    custom_path = _write(tmp_path, "myproject.log", "1000 [ERROR] Boom: it broke\n")

    window._load_log_file(logcat_path)
    tab0 = window._active
    assert tab0.format == "threadtime"

    window._new_tab()
    window._load_log_file(custom_path)
    tab1 = window._active
    assert tab1.format == "MyProject"
    assert tab1.model.entry_at(0).level == "E"

    # Switching back to tab0 must not have disturbed its own parse or format.
    window.tab_bar.setCurrentIndex(0)
    assert window._active is tab0
    assert tab0.format == "threadtime"
    assert tab0.model.entry_at(0).level == "I"


def test_remembered_format_is_reused_without_redetecting(window, tmp_path):
    window._log_formats = [_CUSTOM]
    path = _write(tmp_path, "myproject.log", "1000 [ERROR] Boom: it broke\n")
    window._load_log_file(path)
    assert window._active.format == "MyProject"
    # Remove the format from the configured list, but leave the tab's
    # remembered name in place -- reload must fall back to re-detecting once
    # the remembered name no longer resolves, not crash.
    window._log_formats = []
    window._load_log_file(path)
    assert window.model.rowCount() == 1  # still loads; raw-fallback is fine here


# --- persistence --------------------------------------------------------


def test_tab_format_is_included_in_tab_states(window, tmp_path):
    window._log_formats = [_CUSTOM]
    path = _write(tmp_path, "myproject.log", "1000 [ERROR] Boom: it broke\n")
    window._load_log_file(path)
    states = window._tab_states()
    assert states[0].format == "MyProject"


def test_settings_round_trip_of_log_formats(window, tmp_path):
    from zlog.ui.main_window import MainWindow

    window._log_formats = [_CUSTOM]
    window._save_settings()

    w2 = MainWindow()
    w2._load_and_apply_settings()
    assert w2._log_formats == [_CUSTOM]


# --- the dialog wiring (dialog itself stubbed; see log_format_dialog tests
# for the widget behaviour) -----------------------------------------------


def test_dialog_apply_persists_and_reparses_the_active_tab(window, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QDialog

    from zlog.ui import main_window as mw

    path = _write(tmp_path, "myproject.log", "1000 [ERROR] Boom: it broke\n")
    window._open_log_in_tab(path)  # sets file_path, unlike _load_log_file alone
    assert window.model.entry_at(0).level == ""  # unrecognized before the format exists

    class FakeDialog:
        def __init__(self, formats, parent=None):
            self.formats = formats

        def exec(self):
            return QDialog.Accepted

        def get_values(self):
            return [_CUSTOM]

    monkeypatch.setattr(mw, "LogFormatDialog", FakeDialog)
    window._open_log_format_dialog()

    assert window._log_formats == [_CUSTOM]
    assert window.model.entry_at(0).level == "E"  # re-parsed from disk with the new format


def test_dialog_cancel_changes_nothing(window, monkeypatch):
    from PySide6.QtWidgets import QDialog

    from zlog.ui import main_window as mw

    class FakeDialog:
        def __init__(self, formats, parent=None):
            pass

        def exec(self):
            return QDialog.Rejected

        def get_values(self):
            raise AssertionError("must not be called on cancel")

    monkeypatch.setattr(mw, "LogFormatDialog", FakeDialog)
    window._open_log_format_dialog()
    assert window._log_formats == []


# --- live-reader wiring (adb/follow get no sample to detect against) -------


def test_live_start_uses_no_formats_when_tab_format_is_unset(window):
    assert window._compiled_formats_for_live_start() is None


def test_live_start_reuses_the_tabs_remembered_format(window):
    window._log_formats = [_CUSTOM]
    window._active.format = "MyProject"
    compiled = window._compiled_formats_for_live_start()
    assert compiled is not None and compiled[0].format.name == "MyProject"


def test_live_start_falls_back_when_remembered_format_no_longer_exists(window):
    window._active.format = "Ghost"
    assert window._compiled_formats_for_live_start() is None
