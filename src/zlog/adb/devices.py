"""List attached devices via `adb devices` (subprocess wrapper around the parser).

This is a short, one-shot call (not a stream), so callers may run it on the main
thread. Parsing lives in `zlog.core.devices` so it can be tested without adb.
"""

from __future__ import annotations

import subprocess
import time

from zlog.core.devices import Device, parse_devices

# adb devices has a known race: right after the daemon (re)starts, or right after
# a phone finishes USB enumeration/authorization, the very first call can return
# before the server has caught up, yielding zero rows. One short, bounded retry
# picks up the device without doubling the wait on every genuinely device-less
# Refresh (which only hits this path once, since it's already empty).
_RETRY_DELAY = 0.3


def list_devices(adb_path: str = "adb", timeout: float = 5.0) -> list[Device]:
    """Return the devices `adb` currently sees.

    Raises FileNotFoundError if `adb` isn't on PATH, and
    subprocess.TimeoutExpired if the call hangs past ``timeout``. The caller
    (the UI) maps those to a friendly message.
    """
    devices = _list_devices_once(adb_path, timeout)
    if not devices:
        time.sleep(_RETRY_DELAY)
        devices = _list_devices_once(adb_path, timeout)
    return devices


def _list_devices_once(adb_path: str, timeout: float) -> list[Device]:
    proc = subprocess.run(
        [adb_path, "devices"],
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return parse_devices(proc.stdout)
