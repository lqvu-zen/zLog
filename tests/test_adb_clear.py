"""The clear-buffer adb command is built correctly (no device needed)."""

from zlog.adb import packages


def test_clear_logcat_command(monkeypatch):
    seen = {}

    def fake_run(cmd, **kwargs):
        seen["cmd"] = cmd

        class _Result:
            returncode = 0

        return _Result()

    monkeypatch.setattr(packages.subprocess, "run", fake_run)
    assert packages.clear_logcat("ABC123") is True
    assert seen["cmd"] == ["adb", "-s", "ABC123", "logcat", "-c"]


def test_clear_logcat_no_serial(monkeypatch):
    seen = {}
    monkeypatch.setattr(packages.subprocess, "run", lambda cmd, **kw: seen.update(cmd=cmd))
    packages.clear_logcat(None)
    assert seen["cmd"] == ["adb", "logcat", "-c"]
