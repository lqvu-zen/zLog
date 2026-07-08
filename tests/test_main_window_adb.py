"""The adb-error guard (`_run_adb`) routes failures to a reporter, unchanged."""

from __future__ import annotations

import pytest


@pytest.fixture
def window(qapp, tmp_path, monkeypatch):
    from zlog.ui.main_window import MainWindow

    monkeypatch.setattr(MainWindow, "_settings_path", lambda self: tmp_path / "s.json")
    return MainWindow()


def test_run_adb_returns_result_on_success(window):
    assert window._run_adb(
        lambda: ["ok"], missing_msg="m", error_prefix="e", report=lambda _m: None
    ) == ["ok"]


def test_run_adb_reports_missing_adb(window):
    seen = []
    out = window._run_adb(
        lambda: (_ for _ in ()).throw(FileNotFoundError()),
        missing_msg="adb not found.",
        error_prefix="Could not X",
        report=seen.append,
    )
    assert out is None and seen == ["adb not found."]


def test_run_adb_reports_generic_failure_with_prefix(window):
    seen = []
    out = window._run_adb(
        lambda: (_ for _ in ()).throw(RuntimeError("boom")),
        missing_msg="adb not found.",
        error_prefix="Could not list devices",
        report=seen.append,
    )
    assert out is None and seen == ["Could not list devices: boom"]
