"""Parsing for package/PID resolution — pure, no Qt and no subprocess."""

from __future__ import annotations


def parse_pids(output: str) -> list[str]:
    """Parse the output of `pidof <package>`.

    `pidof` prints the matching PIDs separated by spaces (and a trailing
    newline), or nothing at all when the process isn't running. Multiple
    processes for one package yield multiple PIDs.
    """
    return output.split()


def parse_packages(output: str) -> list[str]:
    """Parse the output of `pm list packages` into sorted package names.

    Each line looks like `package:com.example.app`; the prefix is stripped.
    Blank and non-`package:` lines are ignored.
    """
    names: list[str] = []
    for raw in output.splitlines():
        line = raw.strip()
        if line.startswith("package:"):
            name = line[len("package:") :].strip()
            if name:
                names.append(name)
    return sorted(names)
