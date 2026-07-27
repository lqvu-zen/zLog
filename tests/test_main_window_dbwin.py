"""Windows debug-output capture wired into the window. Off Windows it must report
gracefully and not start anything; the action exists either way."""

from __future__ import annotations

import sys

import pytest


@pytest.fixture
def window(qapp, tmp_path, monkeypatch):
    from zlog.ui.main_window import MainWindow

    monkeypatch.setattr(MainWindow, "_settings_path", lambda self: tmp_path / "s.json")
    return MainWindow()


def test_capture_action_exists(window):
    assert window.capture_debug_act is not None


def test_capture_off_windows_is_graceful(window):
    window.capture_debug_output()
    if sys.platform != "win32":
        assert window._active.reader is None  # nothing started
        assert "Windows" in window.statusBar().currentMessage()


# --- "This PC" in the device box -------------------------------------------
@pytest.fixture
def win_local(window, monkeypatch):
    """A window that believes it's on Windows, so the local-source logic is
    exercised on any platform (the DBWIN *capture* itself stays Windows-only)."""
    import zlog.ui.main_window as mw

    monkeypatch.setattr(mw, "is_supported", lambda: True)
    return window


def test_local_entry_is_first_and_labelled(win_local):
    from zlog.core.devices import Device

    win_local._populate_devices([Device("emulator-5554", "device")])
    assert win_local.device_box.itemText(0) == "This PC (debug output)"
    assert win_local.device_box.itemText(1) == "emulator-5554"


def test_real_device_is_preselected_over_local(win_local):
    from zlog.core.devices import Device

    win_local._populate_devices([Device("emulator-5554", "device")])
    assert win_local.device_box.currentData() == "emulator-5554"


def test_device_count_message_excludes_local(win_local):
    from zlog.core.devices import Device

    win_local._populate_devices([Device("emulator-5554", "device")])
    assert "1 device(s) found" in win_local.statusBar().currentMessage()


def _local_index(window):
    from zlog.core.devices import LOCAL_DBWIN

    return window.device_box.findData(LOCAL_DBWIN)


def test_local_entry_listed_only_on_windows(window):
    present = _local_index(window) >= 0
    assert present == (sys.platform == "win32")


def test_picker_usable_with_no_phone_attached(window):
    """The whole point: on a PC with no device, the box must stay usable."""
    window._populate_devices([])
    if sys.platform == "win32":
        assert window.device_box.isEnabled()
        assert _local_index(window) >= 0
        assert window.start_btn.isEnabled()
    else:
        assert window.device_box.isEnabled() is False  # unchanged behaviour


def test_start_routes_local_source_to_capture(win_local, monkeypatch):
    """Start must call the DBWIN path, never build an AdbReader."""
    from zlog.core.devices import LOCAL_DBWIN, Device

    window = win_local
    window._populate_devices([Device("emulator-5554", "device")])
    window.device_box.setCurrentIndex(window.device_box.findData(LOCAL_DBWIN))

    called = {"capture": 0, "adb": 0}
    monkeypatch.setattr(window, "capture_debug_output", lambda: called.__setitem__("capture", 1))
    monkeypatch.setattr(window, "_start_reader", lambda *a, **k: called.__setitem__("adb", 1))
    window.start()
    assert called == {"capture": 1, "adb": 0}


def test_start_still_uses_adb_for_a_real_device(window, monkeypatch):
    from zlog.core.devices import Device

    window._populate_devices([Device("emulator-5554", "device")])
    idx = window.device_box.findData("emulator-5554")
    window.device_box.setCurrentIndex(idx)

    called = {"capture": 0, "adb": 0}
    monkeypatch.setattr(window, "capture_debug_output", lambda: called.__setitem__("capture", 1))
    monkeypatch.setattr(window, "_start_reader", lambda *a, **k: called.__setitem__("adb", 1))
    window.start()
    assert called == {"capture": 0, "adb": 1}


def test_adb_only_controls_disable_for_local_source(win_local):
    from zlog.core.devices import LOCAL_DBWIN, Device

    window = win_local
    window._populate_devices([Device("emulator-5554", "device")])
    window.device_box.setCurrentIndex(window.device_box.findData(LOCAL_DBWIN))
    assert window.clear_device_btn.isEnabled() is False
    assert window.connect_btn.isEnabled() is False
    assert window.dumpsys_act.isEnabled() is False
    assert window.package_box.isEnabled() is True  # log-driven; works for proc:

    window.device_box.setCurrentIndex(window.device_box.findData("emulator-5554"))
    assert window.clear_device_btn.isEnabled() is True
    assert window.dumpsys_act.isEnabled() is True


def test_merged_view_skips_the_local_entry(window):
    """Regression: start_merged used to call is_serial_streamable() with one
    argument (TypeError). It must now count only real, online devices."""
    from zlog.core.devices import Device

    window._populate_devices([Device("only-one", "device")])
    window.start_merged()  # must not raise
    assert window.capture.extra_readers == []  # one real device -> refused
    assert "at least two" in window.statusBar().currentMessage()
