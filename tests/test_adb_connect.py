"""The adb-connect command is built correctly (no device needed)."""

from zlog.adb import connect as connect_mod


def test_connect_appends_default_port(monkeypatch):
    seen = {}

    def fake_run(cmd, **kwargs):
        seen["cmd"] = cmd

        class _Result:
            stdout = "connected to 192.168.1.5:5555"
            stderr = ""

        return _Result()

    monkeypatch.setattr(connect_mod.subprocess, "run", fake_run)
    msg = connect_mod.connect("192.168.1.5")
    assert seen["cmd"] == ["adb", "connect", "192.168.1.5:5555"]
    assert msg == "connected to 192.168.1.5:5555"


def test_connect_keeps_explicit_port(monkeypatch):
    seen = {}

    def fake_run(cmd, **kwargs):
        seen["cmd"] = cmd

        class _Result:
            stdout = "connected to 192.168.1.5:5556"
            stderr = ""

        return _Result()

    monkeypatch.setattr(connect_mod.subprocess, "run", fake_run)
    connect_mod.connect("192.168.1.5:5556", adb_path="/opt/adb")
    assert seen["cmd"] == ["/opt/adb", "connect", "192.168.1.5:5556"]


def test_connect_falls_back_to_stderr(monkeypatch):
    def fake_run(cmd, **kwargs):
        class _Result:
            stdout = ""
            stderr = "unable to connect to 1.2.3.4:5555"

        return _Result()

    monkeypatch.setattr(connect_mod.subprocess, "run", fake_run)
    msg = connect_mod.connect("1.2.3.4")
    assert msg == "unable to connect to 1.2.3.4:5555"
