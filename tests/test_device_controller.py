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


def test_first_ever_refresh_still_honors_preferred_serial():
    # App startup: no prior refresh baseline, so nothing looks "newly connected"
    # — remember-device.md must keep working on the very first population.
    c = DeviceController()
    c.preferred_serial = "BBB"
    c.set_devices([_dev("AAA"), _dev("BBB")])
    assert c.choose_index() == 1


def test_second_refresh_prefers_a_device_that_just_appeared():
    c = DeviceController()
    c.preferred_serial = "AAA"
    c.set_devices([_dev("AAA")])
    assert c.choose_index() == 0  # baseline refresh: AAA remembered, nothing "new"
    c.set_devices([_dev("AAA"), _dev("BBB")])  # BBB just got plugged in
    assert c.choose_index() == 1  # BBB wins over the remembered AAA


def test_refresh_with_unchanged_devices_still_honors_preferred_serial():
    c = DeviceController()
    c.preferred_serial = "AAA"
    c.set_devices([_dev("AAA"), _dev("BBB")])
    c.set_devices([_dev("AAA"), _dev("BBB")])  # same devices again, nothing new
    assert c.choose_index() == 0  # AAA (remembered), not BBB


def test_unauthorized_becoming_streamable_counts_as_newly_connected():
    c = DeviceController()
    c.preferred_serial = "AAA"
    c.set_devices([_dev("AAA"), _dev("BBB", "unauthorized")])
    assert c.choose_index() == 0  # BBB not streamable yet
    c.set_devices([_dev("AAA"), _dev("BBB", "device")])  # just authorized
    assert c.choose_index() == 1  # BBB now wins, even though its serial was seen before


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
