"""Connect to a device over Wi-Fi via `adb connect` (subprocess wrapper).

A short, one-shot call (not a stream), so callers may run it on the main
thread. Success/failure parsing of adb's reply lives in `zlog.core.devices`
so it can be tested without adb.
"""

from __future__ import annotations

import subprocess

_DEFAULT_PORT = "5555"


def connect(host_port: str, adb_path: str = "adb", timeout: float = 5.0) -> str:
    """Run `adb connect <host_port>` and return adb's own reply message.

    Appends the standard adb-over-Wi-Fi port (5555) when `host_port` has no
    `:port` suffix. Raises FileNotFoundError if `adb` isn't on PATH, and
    subprocess.TimeoutExpired if the call hangs past `timeout`.
    """
    target = host_port if ":" in host_port else f"{host_port}:{_DEFAULT_PORT}"
    proc = subprocess.run(
        [adb_path, "connect", target],
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return (proc.stdout or proc.stderr).strip()
