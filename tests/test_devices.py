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


def test_choose_device_index():
    from zlog.core.devices import choose_device_index

    devs = [Device("AAA", "device"), Device("BBB", "device"), Device("CCC", "offline")]
    assert choose_device_index(devs, None) == 0  # first streamable
    assert choose_device_index(devs, "BBB") == 1  # remembered
    assert choose_device_index(devs, "ZZZ") == 0  # absent -> first streamable
    assert choose_device_index([Device("CCC", "offline")], None) == -1


def test_is_connect_ok():
    from zlog.core.devices import is_connect_ok

    assert is_connect_ok("connected to 192.168.1.5:5555") is True
    assert is_connect_ok("already connected to 192.168.1.5:5555") is True
    assert is_connect_ok("failed to connect to 192.168.1.5:5555") is False
    assert is_connect_ok("unable to connect to 1.2.3.4:5555") is False
    assert is_connect_ok("cannot connect to unix:...") is False
    assert is_connect_ok("") is False


def test_is_serial_streamable():
    from zlog.core.devices import Device, is_serial_streamable

    devs = [Device("AAA", "device"), Device("BBB", "unauthorized")]
    assert is_serial_streamable(devs, "AAA") is True
    assert is_serial_streamable(devs, "BBB") is False  # present but not online
    assert is_serial_streamable(devs, "ZZZ") is False  # absent
    assert is_serial_streamable(devs, None) is True  # any online device (default)
    assert is_serial_streamable([Device("BBB", "offline")], None) is False


# --- local pseudo-source ("This PC") ---------------------------------------
def test_is_local_source():
    from zlog.core.devices import LOCAL_DBWIN, is_local_source

    assert is_local_source(LOCAL_DBWIN) is True
    assert is_local_source("local:anything") is True
    assert is_local_source("emulator-5554") is False
    assert is_local_source("") is False
    assert is_local_source(None) is False


def test_local_device_label_and_flags():
    from zlog.core.devices import local_device

    dev = local_device()
    assert dev.is_local is True
    assert dev.streamable is True  # always available; nothing to connect
    assert dev.label == "This PC (debug output)"


def test_real_device_is_not_local():
    from zlog.core.devices import Device

    assert Device("emulator-5554", "device").is_local is False


def test_choose_index_prefers_a_real_device_over_local():
    from zlog.core.devices import Device, choose_device_index, local_device

    devices = [local_device(), Device("emulator-5554", "device")]
    assert choose_device_index(devices, None) == 1  # the phone, not This PC


def test_choose_index_falls_back_to_local_when_alone():
    from zlog.core.devices import choose_device_index, local_device

    assert choose_device_index([local_device()], None) == 0


def test_choose_index_honors_remembered_local():
    from zlog.core.devices import LOCAL_DBWIN, Device, choose_device_index, local_device

    devices = [local_device(), Device("emulator-5554", "device")]
    assert choose_device_index(devices, LOCAL_DBWIN) == 0


def test_choose_index_remembered_device_still_wins():
    from zlog.core.devices import Device, choose_device_index, local_device

    devices = [local_device(), Device("a", "device"), Device("b", "device")]
    assert choose_device_index(devices, "b") == 2
