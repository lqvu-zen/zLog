"""list_devices retries once on an empty result (the adb-server-race case)."""

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
