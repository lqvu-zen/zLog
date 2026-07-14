"""Parse `adb shell ps` output into a PID -> process/package name map.

Pure (no Qt) so it's unit-testable. Tolerant of both `ps -A -o PID,NAME`
(two columns) and the default multi-column `ps` layout (USER PID PPID ... NAME),
and of a header row.
"""

from __future__ import annotations


def parse_ps(output: str) -> dict[str, str]:
    """Return ``{pid: name}`` from `ps` output; skip headers and junk lines."""
    names: dict[str, str] = {}
    for line in output.splitlines():
        parts = line.split()
        if len(parts) < 2:
            continue
        if parts[0].isdigit():
            pid, name = parts[0], parts[-1]  # "PID NAME" (e.g. -o PID,NAME)
        elif parts[1].isdigit():
            pid, name = parts[1], parts[-1]  # default "USER PID PPID ... NAME"
        else:
            continue  # header line or something unexpected
        if name and not name.isdigit() and name != "NAME":
            names[pid] = name
    return names
