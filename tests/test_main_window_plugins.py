"""_load_plugins' status-bar message: silent in the common (no plugins, no
errors) case so it doesn't clobber a more useful cold-start message (e.g. a
reopened session) — see docs/plans/ui-polish-adb-status.md."""

from __future__ import annotations

import pytest


@pytest.fixture
def window(qapp, tmp_path, monkeypatch):
    from zlog.ui.main_window import MainWindow

    monkeypatch.setattr(MainWindow, "_settings_path", lambda self: tmp_path / "s.json")
    return MainWindow()


def test_no_plugins_leaves_status_bar_message_alone(window, monkeypatch, tmp_path):
    plugins_dir = tmp_path / "plugins"
    monkeypatch.setattr(window, "_plugins_dir", lambda: str(plugins_dir))
    window.statusBar().showMessage("a prior message, e.g. a reopened session")

    window._load_plugins()

    assert window.statusBar().currentMessage() == "a prior message, e.g. a reopened session"


def test_loaded_plugin_reports_in_status_bar(window, monkeypatch, tmp_path):
    plugins_dir = tmp_path / "plugins"
    plugins_dir.mkdir()
    (plugins_dir / "good.py").write_text(
        "def colorize(entry):\n    return None\n", encoding="utf-8"
    )
    monkeypatch.setattr(window, "_plugins_dir", lambda: str(plugins_dir))

    window._load_plugins()

    assert "Loaded 1 colorizer plugin(s)" in window.statusBar().currentMessage()


def test_plugin_load_error_reports_in_status_bar(window, monkeypatch, tmp_path):
    plugins_dir = tmp_path / "plugins"
    plugins_dir.mkdir()
    (plugins_dir / "broken.py").write_text("def colorize(entry): 1/0\nsyntax ???\n")
    monkeypatch.setattr(window, "_plugins_dir", lambda: str(plugins_dir))

    window._load_plugins()

    msg = window.statusBar().currentMessage()
    assert "Loaded 0 colorizer plugin(s)" in msg and "1 failed" in msg
