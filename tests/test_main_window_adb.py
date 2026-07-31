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


# --- refresh_devices() stays usable with no adb (docs/plans/usable-without-adb.md) --


def _fail_with_missing_adb(*_a, **_k):
    raise FileNotFoundError()


def test_refresh_devices_windows_offers_this_pc_when_adb_missing(window, monkeypatch):
    """The bug: refresh_devices() used to return early on a missing adb, so
    _populate_devices (the only place "This PC" is added) never ran and the
    picker/Start stayed dead. Driving the public entry point (not
    _populate_devices directly) is what would have caught it."""
    import zlog.ui.main_window as mw

    monkeypatch.setattr(mw, "is_supported", lambda: True)
    monkeypatch.setattr(mw, "list_devices", _fail_with_missing_adb)

    window.refresh_devices()

    assert window.device_box.isEnabled()
    assert window.device_box.findData("local:dbwin") >= 0
    assert window.start_btn.isEnabled()


def test_refresh_devices_non_windows_still_shows_no_devices_when_adb_missing(window, monkeypatch):
    """Off Windows there's no local source to fall back to, so the disabled
    "No devices" picker is unchanged from before this fix."""
    import zlog.ui.main_window as mw

    monkeypatch.setattr(mw, "is_supported", lambda: False)
    monkeypatch.setattr(mw, "list_devices", _fail_with_missing_adb)

    window.refresh_devices()

    assert window.device_box.isEnabled() is False
    assert window.device_box.itemText(0) == "No devices"
    assert window.start_btn.isEnabled() is False


def test_refresh_devices_missing_adb_message_shown_once(window, monkeypatch):
    """A Windows-only user shouldn't be nagged about Android tooling on every
    Refresh; the informational message is a one-shot until adb comes back."""
    import zlog.ui.main_window as mw

    monkeypatch.setattr(mw, "is_supported", lambda: True)
    monkeypatch.setattr(mw, "list_devices", _fail_with_missing_adb)
    window._adb_missing_reported = False  # deterministic regardless of the test machine's adb

    window.refresh_devices()
    first = window.statusBar().currentMessage()
    assert "adb not found" in first

    window.statusBar().clearMessage()
    window.refresh_devices()
    second = window.statusBar().currentMessage()
    assert "adb not found" not in second  # not repeated

    monkeypatch.setattr(mw, "list_devices", lambda *_a, **_k: [])
    window.refresh_devices()  # adb is back; re-arms the one-shot notice

    monkeypatch.setattr(mw, "list_devices", _fail_with_missing_adb)
    window.refresh_devices()
    third = window.statusBar().currentMessage()
    assert "adb not found" in third


def test_refresh_devices_generic_adb_failure_reported_every_time(window, monkeypatch):
    """A real, ongoing adb problem (as opposed to adb simply not being
    installed) must keep being reported — the message just stops being framed
    as fatal (This PC still offered on Windows)."""
    import zlog.ui.main_window as mw

    monkeypatch.setattr(mw, "is_supported", lambda: True)
    monkeypatch.setattr(
        mw, "list_devices", lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("boom"))
    )

    window.refresh_devices()
    assert "Could not list devices: boom" in window.statusBar().currentMessage()
    window.statusBar().clearMessage()
    window.refresh_devices()
    assert "Could not list devices: boom" in window.statusBar().currentMessage()
    assert window.device_box.findData("local:dbwin") >= 0  # still usable
