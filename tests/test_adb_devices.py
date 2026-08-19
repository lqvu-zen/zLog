"""list_devices retries once on an empty result (the adb-server-race case);
device_abi is a best-effort getprop wrapper for native symbol resolution."""

import subprocess

from zlog.adb import devices as devices_mod


def _result(stdout: str):
    class _Result:
        pass

    r = _Result()
    r.stdout = stdout
    r.stderr = ""
    return r


def test_returns_devices_from_first_call_without_retry(monkeypatch):
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        return _result("List of devices attached\nemulator-5554\tdevice\n")

    monkeypatch.setattr(devices_mod.subprocess, "run", fake_run)
    monkeypatch.setattr(devices_mod.time, "sleep", lambda _s: None)
    devices = devices_mod.list_devices()
    assert [d.serial for d in devices] == ["emulator-5554"]
    assert len(calls) == 1  # no retry needed


def test_retries_once_when_first_call_is_empty(monkeypatch):
    outputs = iter(
        [
            "List of devices attached\n",  # daemon just (re)started; not caught up yet
            "List of devices attached\nABC123\tdevice\n",
        ]
    )
    calls = []
    slept = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        return _result(next(outputs))

    monkeypatch.setattr(devices_mod.subprocess, "run", fake_run)
    monkeypatch.setattr(devices_mod.time, "sleep", slept.append)
    devices = devices_mod.list_devices()
    assert [d.serial for d in devices] == ["ABC123"]
    assert len(calls) == 2
    assert slept == [devices_mod._RETRY_DELAY]


def test_genuinely_empty_stays_empty_after_one_retry(monkeypatch):
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        return _result("List of devices attached\n")

    monkeypatch.setattr(devices_mod.subprocess, "run", fake_run)
    monkeypatch.setattr(devices_mod.time, "sleep", lambda _s: None)
    devices = devices_mod.list_devices()
    assert devices == []
    assert len(calls) == 2  # exactly one retry, not an infinite loop


def test_device_abi_returns_the_property_value(monkeypatch):
    def fake_run(cmd, **kwargs):
        assert cmd[-1] == "ro.product.cpu.abi"
        return _result("arm64-v8a\n")

    monkeypatch.setattr(devices_mod.subprocess, "run", fake_run)
    assert devices_mod.device_abi("emulator-5554") == "arm64-v8a"


def test_device_abi_returns_none_on_empty_property(monkeypatch):
    monkeypatch.setattr(devices_mod.subprocess, "run", lambda cmd, **kw: _result(""))
    assert devices_mod.device_abi("emulator-5554") is None


def test_device_abi_returns_none_when_adb_is_missing(monkeypatch):
    def fake_run(cmd, **kwargs):
        raise OSError("adb not found")

    monkeypatch.setattr(devices_mod.subprocess, "run", fake_run)
    assert devices_mod.device_abi("emulator-5554") is None


def test_device_abi_returns_none_on_timeout(monkeypatch):
    def fake_run(cmd, **kwargs):
        raise subprocess.TimeoutExpired(cmd, kwargs.get("timeout", 5.0))

    monkeypatch.setattr(devices_mod.subprocess, "run", fake_run)
    assert devices_mod.device_abi("emulator-5554") is None
