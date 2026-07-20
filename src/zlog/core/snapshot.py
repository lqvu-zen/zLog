"""Build `adb shell dumpsys` argv — pure, no Qt/subprocess, so it's unit-testable.

A one-shot device snapshot (`dumpsys`, optionally a single service like `battery`
or `meminfo`) captured alongside a log gives context when debugging.
"""

from __future__ import annotations


def dumpsys_args(section: str = "") -> list[str]:
    """Return the `shell dumpsys [section]` argv tail.

    An empty/whitespace `section` dumps everything; otherwise the first token is
    taken as the service name (extra words are ignored so a stray space can't turn
    into an injected argument).
    """
    section = (section or "").strip()
    if not section:
        return ["shell", "dumpsys"]
    return ["shell", "dumpsys", section.split()[0]]
