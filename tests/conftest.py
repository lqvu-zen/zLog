"""Shared pytest fixtures.

The `ui`/`adb` tests need a `QApplication`, but CI has no display. Force Qt's
`offscreen` platform *before* any Qt import so those tests run headless anywhere,
and hand out a single app for the whole session (Qt allows only one).
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest


@pytest.fixture(scope="session")
def qapp():
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app
