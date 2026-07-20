"""One-shot `adb shell dumpsys` capture. Parsing/argv building live in
`zlog.core.snapshot` so they're testable without adb."""

from __future__ import annotations

import subprocess

from zlog.core.snapshot import dumpsys_args


def capture_dumpsys(
    serial: str | None,
    section: str = "",
    adb_path: str = "adb",
    timeout: float = 30.0,
) -> str:
    """Return the device's `dumpsys` output (optionally for a single service).

    Raises FileNotFoundError if adb is missing and subprocess.TimeoutExpired if the
    device is slow; the caller reports either to the user.
    """
    cmd = [adb_path]
    if serial:
        cmd += ["-s", serial]
    cmd += dumpsys_args(section)
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    return proc.stdout
