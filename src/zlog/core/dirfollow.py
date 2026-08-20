"""Pick the newest file matching a glob in a directory, and decide when a
rotation's replacement has stabilized enough to switch to it — pure, no Qt or
threads, so both are unit-testable in isolation from the actual polling loop.
See docs/plans/directory-glob-follow.md.
"""

from __future__ import annotations

import os
from glob import glob


def pick_newest(dir_path: str, pattern: str) -> str | None:
    """The newest file in `dir_path` matching `pattern` (a glob like `*.log`),
    or None if nothing matches.

    Ties (same mtime — a coarse-resolution filesystem, or a bulk copy that
    preserves timestamps) break on the lexicographically largest name: a
    deterministic rule, rather than depending on `glob`'s unspecified order. A
    file that vanishes between listing and stat'ing (a rotation script
    deleting the old one mid-poll) is skipped rather than raising.
    """
    candidates = []
    for path in glob(os.path.join(dir_path, pattern)):
        try:
            mtime = os.path.getmtime(path)
        except OSError:
            continue
        candidates.append((mtime, os.path.basename(path), path))
    if not candidates:
        return None
    return max(candidates)[2]


def should_switch(old_file_stable_for: float, threshold: float) -> bool:
    """True once the currently-followed file has stopped growing for at least
    `threshold` seconds.

    This grace period is what keeps a rotation script creating a fresh file a
    moment before the app actually starts writing to it from causing an early
    swap to an empty-looking file while the old one still has trailing lines
    (see the plan's Risks section).
    """
    return old_file_stable_for >= threshold
