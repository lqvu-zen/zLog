"""Resolve packages to PIDs and list installed packages via `adb shell`.

Both are short, one-shot calls (not streams), so callers may run them on the
main thread with a timeout. Parsing lives in `zlog.core.packages` so it stays
testable without adb.
"""

from __future__ import annotations

import subprocess

from zlog.core.packages import parse_packages, parse_pids


def _base(adb_path: str, serial: str | None) -> list[str]:
    cmd = [adb_path]
    if serial:
        cmd += ["-s", serial]
    return cmd


def resolve_pids(
    serial: str | None, package: str, adb_path: str = "adb", timeout: float = 5.0
) -> list[str]:
    """Return the current PID(s) for ``package`` on the device (empty if not running)."""
    proc = subprocess.run(
        _base(adb_path, serial) + ["shell", "pidof", package],
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return parse_pids(proc.stdout)


def list_packages(serial: str | None, adb_path: str = "adb", timeout: float = 10.0) -> list[str]:
    """Return the device's third-party package names, sorted."""
    proc = subprocess.run(
        _base(adb_path, serial) + ["shell", "pm", "list", "packages", "-3"],
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return parse_packages(proc.stdout)


def clear_logcat(serial: str | None, adb_path: str = "adb", timeout: float = 10.0) -> bool:
    """Clear the device's logcat ring buffer (`adb logcat -c`). Returns True on
    success; raises CalledProcessError on a non-zero exit."""
    subprocess.run(
        _base(adb_path, serial) + ["logcat", "-c"],
        capture_output=True,
        text=True,
        timeout=timeout,
        check=True,
    )
    return True
