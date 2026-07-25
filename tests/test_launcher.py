"""LaunchReader end-to-end with a real child process (cross-platform, so the
capture path is genuinely exercised here, not just mocked)."""

from __future__ import annotations

import sys

from zlog.winlog.launcher import LaunchReader, build_argv, should_flush
from zlog.winlog.processes import list_processes


def _run_and_collect(qapp, argv, timeout_ms=10000):
    """Run a child to completion, returning every LogEntry it produced."""
    from PySide6.QtCore import QEventLoop, QTimer

    reader = LaunchReader(argv)
    got: list = []
    reader.batch_ready.connect(got.extend)
    loop = QEventLoop()
    reader.finished.connect(loop.quit)
    QTimer.singleShot(timeout_ms, loop.quit)  # never hang the suite
    reader.start()
    loop.exec()
    reader.stop()
    return got


def test_build_argv_keeps_exe_alone():
    assert build_argv("C:\\Program Files\\my app.exe") == ["C:\\Program Files\\my app.exe"]


def test_build_argv_splits_arguments():
    assert build_argv("app.exe", "--flag value") == ["app.exe", "--flag", "value"]


def test_should_flush_rules():
    assert should_flush(0, 99) is False
    assert should_flush(1, 0.0) is False
    assert should_flush(1, 0.5) is True
    assert should_flush(500, 0.0) is True


def test_app_name_is_basename():
    r = LaunchReader(["/usr/bin/python3"])
    assert r.app_name == "python3"


def test_captures_child_stdout(qapp):
    entries = _run_and_collect(qapp, [sys.executable, "-c", "print('hello from child')"])
    assert any(e.message == "hello from child" for e in entries)


def test_captures_stderr_too(qapp):
    code = "import sys; sys.stderr.write('boom on stderr\\n')"
    entries = _run_and_collect(qapp, [sys.executable, "-c", code])
    assert any("boom on stderr" in e.message for e in entries)


def test_entry_fields_are_mapped(qapp):
    entries = _run_and_collect(qapp, [sys.executable, "-c", "print('plain line')"])
    entry = next(e for e in entries if e.message == "plain line")
    assert entry.source == "stdout"
    assert entry.tag  # the executable's base name
    assert entry.pid.isdigit() and int(entry.pid) > 0
    assert entry.time  # stamped on arrival
    assert entry.level == "I"


def test_level_inferred_from_text(qapp):
    entries = _run_and_collect(qapp, [sys.executable, "-c", "print('fatal error: nope')"])
    entry = next(e for e in entries if "nope" in e.message)
    assert entry.level == "E"


def test_bad_executable_reports_error(qapp):
    from PySide6.QtCore import QEventLoop, QTimer

    reader = LaunchReader(["definitely-not-a-real-binary-xyz"])
    errors: list[str] = []
    reader.error.connect(errors.append)
    loop = QEventLoop()
    reader.finished.connect(loop.quit)
    QTimer.singleShot(10000, loop.quit)
    reader.start()
    loop.exec()
    assert errors and "Could not launch" in errors[0]


def test_stop_terminates_a_long_running_child(qapp):
    reader = LaunchReader([sys.executable, "-c", "import time; time.sleep(30)"])
    reader.start()
    while reader.pid == 0 and reader.isRunning():  # wait for Popen to report a pid
        qapp.processEvents()
    reader.stop()
    assert not reader.isRunning()  # thread joined, child terminated


def test_list_processes_off_windows_is_empty():
    if sys.platform != "win32":
        assert list_processes() == []
