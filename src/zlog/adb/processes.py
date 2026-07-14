"""Fetch a PID -> process-name map from a device via `adb shell ps`.

Kept out of `core/` because it shells out; the parsing itself lives in
`core.processes.parse_ps` and is unit-tested there.
"""

from __future__ import annotations

import subprocess

from zlog.core.processes import parse_ps


def list_process_map(serial: str | None, adb_path: str = "adb", timeout: float = 4.0) -> dict:
    """Return ``{pid: name}`` for the device's running processes (or ``{}``).

    Tries the explicit two-column form first; if the device's ``ps`` ignores the
    options and prints nothing useful, falls back to a bare ``ps``.
    """
    base = [adb_path]
    if serial:
        base += ["-s", serial]

    def run(args):
        out = subprocess.run(base + args, capture_output=True, text=True, timeout=timeout).stdout
        return parse_ps(out or "")

    names = run(["shell", "ps", "-A", "-o", "PID,NAME"])
    if not names:
        names = run(["shell", "ps", "-A"])
    if not names:
        names = run(["shell", "ps"])
    return names
