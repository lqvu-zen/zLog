"""Tests for device-list parsing. No Qt, no adb, no display required."""

from zlog.core.devices import Device, parse_devices


def test_parses_multiple_devices():
    out = "List of devices attached\nemulator-5554\tdevice\n0A2B\tdevice\n"
    assert parse_devices(out) == [
        Device("emulator-5554", "device"),
        Device("0A2B", "device"),
    ]


def test_empty_when_only_header():
    assert parse_devices("List of devices attached\n\n") == []


def test_offline_and_unauthorized_are_not_streamable():
    out = "List of devices attached\nX1\toffline\nX2\tunauthorized\n"
    devices = parse_devices(out)
    assert [d.state for d in devices] == ["offline", "unauthorized"]
    assert all(not d.streamable for d in devices)


def test_streamable_flag_and_label():
    ready = Device("emulator-5554", "device")
    assert ready.streamable
    assert ready.label == "emulator-5554"
    unauth = Device("X2", "unauthorized")
    assert not unauth.streamable
    assert unauth.label == "X2 (unauthorized)"


def test_ignores_daemon_noise_lines():
    out = (
        "* daemon not running; starting now at tcp:5037\n"
        "* daemon started successfully\n"
        "List of devices attached\n"
        "ABC\tdevice\n"
    )
    assert parse_devices(out) == [Device("ABC", "device")]
