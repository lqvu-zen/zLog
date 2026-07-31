"""Tests for adb resolution order. No Qt, no filesystem, no adb required."""

from zlog.core.adbpath import managed_adb_path, resolve_adb


def test_setting_wins_over_everything():
    assert resolve_adb("C:/my/adb.exe", lambda: "C:/path/adb", lambda: "C:/managed/adb") == (
        "C:/my/adb.exe",
        "setting",
    )


def test_path_wins_over_managed():
    assert resolve_adb("", lambda: "C:/path/adb", lambda: "C:/managed/adb") == (
        "C:/path/adb",
        "path",
    )


def test_managed_used_when_nothing_else_found():
    assert resolve_adb("", lambda: None, lambda: "C:/managed/adb") == (
        "C:/managed/adb",
        "managed",
    )


def test_falls_back_to_bare_adb_when_nothing_found():
    """Nothing resolves anywhere: fall back to the bare "adb" command so a
    missing adb still fails the same clear way it always has (see
    docs/plans/usable-without-adb.md) rather than a new one."""
    assert resolve_adb("", lambda: None, lambda: None) == ("adb", "none")


def test_managed_adb_path_windows(monkeypatch):
    import zlog.core.adbpath as adbpath

    monkeypatch.setattr(adbpath.sys, "platform", "win32")
    assert managed_adb_path("C:/appdata") == "C:\\appdata\\platform-tools\\adb.exe"


def test_managed_adb_path_non_windows(monkeypatch):
    import zlog.core.adbpath as adbpath

    monkeypatch.setattr(adbpath.sys, "platform", "linux")
    assert managed_adb_path("/home/u/appdata") == "/home/u/appdata/platform-tools/adb"
