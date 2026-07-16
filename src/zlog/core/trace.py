"""Detect Java stack-trace frame lines for folding — pure, no Qt.

A logcat crash dump interleaves an exception header with its stack frames:

    E AndroidRuntime: FATAL EXCEPTION: main
    E AndroidRuntime: java.lang.RuntimeException: Unable to start activity
    E AndroidRuntime:     at android.app.ActivityThread.performLaunch(...)
    E AndroidRuntime:     at android.app.ActivityThread.handleLaunch(...)
    E AndroidRuntime:     ... 27 more

The `at …` and `… N more` lines are the frames; folding hides them under their
header (the nearest preceding non-frame line).
"""

from __future__ import annotations

import re

_FRAME_RE = re.compile(r"^\s*(?:at\s|\.\.\.\s+\d+\s+more\b)")


def is_stack_frame(message: str) -> bool:
    """True for a Java stack-frame continuation line (`at …` or `… N more`)."""
    return _FRAME_RE.match(message) is not None


def frame_hint(n: int) -> str:
    """Short disclosure hint for a folded trace, e.g. ``"… 27 frames"``."""
    return f"… {n} frame{'s' if n != 1 else ''}"
