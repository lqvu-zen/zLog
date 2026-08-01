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
