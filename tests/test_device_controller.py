"""Unit tests for DeviceController — no MainWindow, no QApplication needed
(a bare QObject requires neither)."""

from __future__ import annotations

from zlog.core.devices import Device
from zlog.core.models import LogEntry
from zlog.ui.device_controller import DeviceController


def _dev(serial, state="device"):
    return Device(serial, state)


def _proc_start(pid, package):
    return LogEntry(
        "12:00:00.000", "1", "1", "I", "ActivityManager", f"Start proc {pid}:{package}/u0a1 for x"
    )


def test_choose_index_first_streamable_when_no_preference():
    c = DeviceController()
    c.set_devices([_dev("AAA"), _dev("BBB")])
    assert c.choose_index() == 0


def test_choose_index_prefers_remembered_serial():
    c = DeviceController()
    c.preferred_serial = "BBB"
    c.set_devices([_dev("AAA"), _dev("BBB")])
    assert c.choose_index() == 1


def test_choose_index_absent_preference_falls_back():
    c = DeviceController()
    c.preferred_serial = "ZZZ"
    c.set_devices([_dev("AAA"), _dev("BBB")])
    assert c.choose_index() == 0


def test_choose_index_skips_unstreamable():
    c = DeviceController()
    c.set_devices([_dev("AAA", "unauthorized"), _dev("BBB")])
    assert c.choose_index() == 1  # index 0 isn't streamable


def test_choose_index_none_when_nothing_streamable():
    c = DeviceController()
    c.set_devices([_dev("AAA", "offline")])
    assert c.choose_index() == -1


def test_remember_ignores_none_but_keeps_real():
    c = DeviceController()
    c.remember("AAA")
    c.remember(None)  # the 'No devices' placeholder must not wipe the memory
    assert c.preferred_serial == "AAA"


def test_apply_and_clear_filter():
    c = DeviceController()
    assert c.filtering is False
    c.apply_filter("com.example", ["100", "101"])
    assert c.filtering is True and c.filter_pids == {"100", "101"}
    c.clear_filter()
    assert c.filtering is False and c.filter_pids == set()


def test_track_adds_new_pids_for_filtered_package():
    c = DeviceController()
    c.apply_filter("com.example", ["100"])
    added = c.track([_proc_start("200", "com.example"), _proc_start("300", "com.other")])
    assert added == ["200"]
    assert c.filter_pids == {"100", "200"}


def test_track_noop_without_filter():
    c = DeviceController()
    assert c.track([_proc_start("200", "com.example")]) == []
