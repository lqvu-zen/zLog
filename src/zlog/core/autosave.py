"""Autosave rotation helpers — pure (string/arithmetic only), so unit-testable.

The UI performs the actual file writes; these only decide *when* to roll the file
over and *what* the rolled-over path is called.
"""

from __future__ import annotations

import os

AUTOSAVE_CAP = 10 * 1024 * 1024  # bytes before rolling over to a single .1 backup


def rotate_path(path: str) -> str:
    """The rolled-over name: insert '.1' before the extension (a.log -> a.1.log)."""
    root, ext = os.path.splitext(path)
    return f"{root}.1{ext}"


def should_rotate(current_size: int, incoming_bytes: int, cap: int = AUTOSAVE_CAP) -> bool:
    """True if appending `incoming_bytes` would push the file past `cap`."""
    return cap > 0 and current_size + incoming_bytes > cap
