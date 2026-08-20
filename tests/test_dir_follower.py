"""DirFollower against real files: initial read, growth, swap to a newer file,
stop. Cross-platform, real threads — mirrors tests/test_file_follower.py's
approach so the actual poll/swap loop is exercised, not just its pure helpers.
"""

from __future__ import annotations

import os
import time

from PySide6.QtCore import QEventLoop, QTimer

from zlog.ui.dir_follower import DirFollower

LINE = "06-30 12:00:0{n}.000 1 2 I Tag: line{n}\n"


def _messages(entries):
    return [e.message for e in entries]


def _wait_for(qapp, predicate, timeout_ms=6000):
    """Spin the event loop until `predicate()` or the timeout (never hang CI)."""
    loop = QEventLoop()
    elapsed = {"ms": 0}

    def tick():
        elapsed["ms"] += 50
        if predicate() or elapsed["ms"] >= timeout_ms:
            loop.quit()

    timer = QTimer()
    timer.timeout.connect(tick)
    timer.start(50)
    loop.exec()
    timer.stop()
    return predicate()


def _start(qapp, dir_path, pattern, **kw):
    reader = DirFollower(str(dir_path), pattern, **kw)
    got: list = []
    switches: list = []
    reader.batch_ready.connect(got.extend)
    reader.switched.connect(switches.append)
    reader.start()
    return reader, got, switches


def test_reads_existing_content_then_follows(qapp, tmp_path):
    (tmp_path / "app-1.log").write_text(LINE.format(n=1), encoding="utf-8")
    reader, got, _ = _start(qapp, tmp_path, "app-*.log")
    try:
        assert _wait_for(qapp, lambda: len(got) >= 1)
        assert "line1" in _messages(got)[0]

        with open(tmp_path / "app-1.log", "a", encoding="utf-8") as fh:
            fh.write(LINE.format(n=2))
        assert _wait_for(qapp, lambda: len(got) >= 2)
        assert any("line2" in m for m in _messages(got))
    finally:
        reader.stop()


def test_swaps_to_a_newer_file_after_it_stabilizes(qapp, tmp_path):
    (tmp_path / "app-1.log").write_text(LINE.format(n=1), encoding="utf-8")
    reader, got, switches = _start(qapp, tmp_path, "app-*.log")
    try:
        assert _wait_for(qapp, lambda: len(got) >= 1)

        now = time.time()
        os.utime(tmp_path / "app-1.log", (now, now))
        newer = tmp_path / "app-2.log"
        newer.write_text(LINE.format(n=2), encoding="utf-8")
        os.utime(newer, (now + 10, now + 10))  # unambiguously newer

        # The switch fires only after app-2.log has stopped growing for the
        # grace period, so this must be given enough time in the event loop
        # (the default timeout comfortably covers _SWITCH_GRACE).
        assert _wait_for(qapp, lambda: len(switches) >= 1)
        assert switches[0] == "app-2.log"
        assert reader.current_path == str(newer)
        assert _wait_for(qapp, lambda: any("line2" in m for m in _messages(got)))

        # Content written to app-1.log after the swap must not reappear.
        with open(tmp_path / "app-1.log", "a", encoding="utf-8") as fh:
            fh.write(LINE.format(n=99))
        _wait_for(qapp, lambda: False, timeout_ms=800)
        assert not any("line99" in m for m in _messages(got))
    finally:
        reader.stop()


def test_no_matching_files_reports_error(qapp, tmp_path):
    reader = DirFollower(str(tmp_path), "*.log")
    errors = []
    reader.error.connect(errors.append)
    reader.start()
    try:
        assert _wait_for(qapp, lambda: len(errors) >= 1)
        assert "No files match" in errors[0]
    finally:
        reader.stop()


def test_stop_ends_the_thread_promptly(qapp, tmp_path):
    (tmp_path / "app.log").write_text(LINE.format(n=1), encoding="utf-8")
    reader, got, _ = _start(qapp, tmp_path, "*.log")
    assert _wait_for(qapp, lambda: len(got) >= 1)
    reader.stop()
    assert not reader.isRunning()


def test_name_is_the_pattern():
    reader = DirFollower("C:/logs", "app-*.log")
    assert reader.name == "app-*.log"


# --- window wiring -----------------------------------------------------------


def test_follow_folder_starts_a_reader_in_a_tab(qapp, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QFileDialog, QInputDialog

    from zlog.ui.main_window import MainWindow

    monkeypatch.setattr(MainWindow, "_settings_path", lambda self: tmp_path / "s.json")
    (tmp_path / "app-1.log").write_text(LINE.format(n=1), encoding="utf-8")
    monkeypatch.setattr(QFileDialog, "getExistingDirectory", lambda *a, **k: str(tmp_path))
    monkeypatch.setattr(QInputDialog, "getText", staticmethod(lambda *a, **k: ("app-*.log", True)))

    window = MainWindow()
    try:
        window.follow_folder()
        assert window._active.reader is not None
        assert window._active.stream_label == "app-*.log"
        assert window.stop_btn.isEnabled()
    finally:
        window.stop()
    assert window._active.reader is None  # Stop tore the follower down


def test_follow_folder_no_match_starts_nothing(qapp, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QFileDialog, QInputDialog

    from zlog.ui.main_window import MainWindow

    monkeypatch.setattr(MainWindow, "_settings_path", lambda self: tmp_path / "s.json")
    monkeypatch.setattr(QFileDialog, "getExistingDirectory", lambda *a, **k: str(tmp_path))
    monkeypatch.setattr(QInputDialog, "getText", staticmethod(lambda *a, **k: ("*.log", True)))

    window = MainWindow()
    window.follow_folder()
    assert window._active.reader is None
    assert "No files match" in window.statusBar().currentMessage()


def test_follow_folder_cancelled_folder_picker_does_nothing(qapp, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QFileDialog

    from zlog.ui.main_window import MainWindow

    monkeypatch.setattr(MainWindow, "_settings_path", lambda self: tmp_path / "s.json")
    monkeypatch.setattr(QFileDialog, "getExistingDirectory", lambda *a, **k: "")

    window = MainWindow()
    window.follow_folder()
    assert window._active.reader is None


def test_dir_follower_switch_shows_status_note(qapp, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QFileDialog, QInputDialog

    from zlog.ui.main_window import MainWindow

    monkeypatch.setattr(MainWindow, "_settings_path", lambda self: tmp_path / "s.json")
    (tmp_path / "app-1.log").write_text(LINE.format(n=1), encoding="utf-8")
    monkeypatch.setattr(QFileDialog, "getExistingDirectory", lambda *a, **k: str(tmp_path))
    monkeypatch.setattr(QInputDialog, "getText", staticmethod(lambda *a, **k: ("app-*.log", True)))

    window = MainWindow()
    try:
        window.follow_folder()
        window._on_dir_follower_switched("app-2.log")
        assert window.statusBar().currentMessage() == "Switched to newest file: app-2.log"
    finally:
        window.stop()
