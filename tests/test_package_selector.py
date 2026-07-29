"""Log-driven + running-process App selector: two-way sync with proc: token."""

from __future__ import annotations

import pytest

from zlog.core.models import LogEntry


@pytest.fixture
def window(qapp, tmp_path, monkeypatch):
    import zlog.winlog.processes as processes
    from zlog.ui.main_window import MainWindow

    monkeypatch.setattr(MainWindow, "_settings_path", lambda self: tmp_path / "s.json")
    # Deterministic Load: no running processes unless a test injects some —
    # otherwise this machine's real process list would leak into assertions.
    monkeypatch.setattr(processes, "list_processes", lambda: [])
    return MainWindow()


def _seed(window):
    window.model.append_entries(
        [
            LogEntry("t", "100", "1", "I", "T", "a"),
            LogEntry("t", "200", "1", "I", "T", "b"),
        ]
    )
    window.model.merge_process_names({"100": "com.example.app", "200": "com.other"})


def test_load_fills_dropdown_from_log(window):
    _seed(window)
    window.load_packages()
    items = [window.package_box.itemText(i) for i in range(window.package_box.count())]
    assert items == ["com.example.app", "com.other"]  # from the log, sorted


def test_load_includes_running_processes_marking_the_overlap(window, monkeypatch):
    import zlog.winlog.processes as processes
    from zlog.core.procinfo import ProcessInfo

    _seed(window)
    monkeypatch.setattr(processes, "list_processes", lambda: [ProcessInfo(999, "com.other")])
    window.load_packages()
    items = [window.package_box.itemText(i) for i in range(window.package_box.count())]
    assert items == ["com.example.app", "com.other ●"]  # log + running, overlap marked


def test_load_status_reports_both_sources(window, monkeypatch):
    import zlog.winlog.processes as processes
    from zlog.core.procinfo import ProcessInfo

    _seed(window)
    monkeypatch.setattr(processes, "list_processes", lambda: [ProcessInfo(1, "x.exe")])
    window.load_packages()
    assert window.statusBar().currentMessage() == "2 from the log, 1 running."


def test_apply_sets_proc_token_and_filters(window):
    _seed(window)
    window.package_box.setEditText("com.example.app")
    window.apply_package_filter()
    assert "proc:com.example.app" in window.query.text()
    assert window.proxy.rowCount() == 1  # only pid 100's row


def test_apply_strips_running_marker(window):
    _seed(window)
    window.package_box.setEditText("com.example.app ●")
    window.apply_package_filter()
    assert "proc:com.example.app" in window.query.text()
    assert "●" not in window.query.text()


def test_query_proc_token_mirrors_into_box(window):
    _seed(window)
    window.query.setText("proc:com.other")
    window._apply_query()
    assert window.package_box.currentText() == "com.other"


def test_package_token_aliases_proc(window):
    _seed(window)
    window.query.setText("package:com.example.app")
    window._apply_query()
    assert window.proxy.rowCount() == 1
    assert window.package_box.currentText() == "com.example.app"


def test_clear_pkg_removes_token_and_empties_box(window):
    _seed(window)
    window.package_box.setEditText("com.example.app")
    window.apply_package_filter()
    window.clear_package_filter()
    assert "proc:" not in window.query.text()
    assert window.package_box.currentText() == ""
    assert window.proxy.rowCount() == 2  # unfiltered again
