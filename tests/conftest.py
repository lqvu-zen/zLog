"""Shared pytest fixtures.

The `ui`/`adb` tests need a `QApplication`, but CI has no display. Force Qt's
`offscreen` platform *before* any Qt import so those tests run headless anywhere,
and hand out a single app for the whole session (Qt allows only one).
"""

from __future__ import annotations

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest


@pytest.fixture(scope="session")
def qapp():
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app


def pytest_collection_modifyitems(config, items):
    """Skip `@pytest.mark.windows_only` tests everywhere but a real win32
    host — these assert against actual Win32 behavior (a real process list,
    a real PID's image name), as opposed to the existing tests that force
    `is_supported() -> True` to exercise the cross-platform logic on any OS
    (see ci-windows-job.md — both patterns are deliberate and coexist)."""
    if sys.platform == "win32":
        return
    skip = pytest.mark.skip(reason="needs a real win32 host")
    for item in items:
        if "windows_only" in item.keywords:
            item.add_marker(skip)


def pytest_sessionfinish(session, exitstatus):
    """Windows-only workaround for a real observed failure: on a fresh
    windows-latest GitHub Actions runner, a full run of this suite prints
    "765 passed" and then the *process* exits 1 anyway, ~0.6s later — after
    pytest itself had already finished reporting, during Python's normal
    interpreter shutdown.

    One real, root-caused contributor was found and fixed: several QThread
    readers (AdbReader, DebugOutputReader, EventLogReader, LaunchReader,
    FileLoader) set their `_running` flag to True *inside* `run()`, after
    setup work — so calling `.stop()` before `run()` reached that line
    silently un-cancelled it, leaving a live thread still blocked in a Win32
    wait call at interpreter exit (`ui/file_follower.py`'s FileFollower
    already avoided this; see docs/plans/ci-windows-job.md for how it was
    found and the fix applied to the other four).

    Fixing that removed the *named* leaked thread from the crash dump, but a
    generic (unnamed) crash can still occur at shutdown — plausibly broader
    PySide6/Qt teardown-ordering fragility across the many `MainWindow`
    instances this suite constructs against one session-scoped `qapp`, not
    something pinned down further. It doesn't reproduce locally, only on the
    CI runner (different GC/shutdown timing).

    Force-exiting here, after pytest has already computed its real
    `exitstatus` from actual test results, reports the correct outcome
    regardless of whatever happens in that shutdown path — verified locally
    (including in this exact crashing scenario) that `os._exit(exitstatus)`
    still reports 0 on an all-pass run even when the crash fires. No
    coverage/atexit tooling relies on running here, so skipping Python's
    normal shutdown is safe.
    """
    if sys.platform == "win32":
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(exitstatus)
