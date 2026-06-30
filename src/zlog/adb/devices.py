"""List attached devices via `adb devices` (subprocess wrapper around the parser).

This is a short, one-shot call (not a stream), so callers may run it on the main
thread. Parsing lives in `zlog.core.devices` so it can be tested without adb.
"""

from __future__ import annotations

import subprocess

from zlog.core.devices import Device, parse_devices


def list_devices(adb_path: str = "adb", timeout: float = 5.0) -> list[Device]:
    """Return the devices `adb` currently sees.

    Raises FileNotFoundError if `adb` isn't on PATH, and
    subprocess.TimeoutExpired if the call hangs past ``timeout``. The caller
    (the UI) maps those to a friendly message.
    """
    proc = subprocess.run(
        [adb_path, "devices"],
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return parse_devices(proc.stdout)
