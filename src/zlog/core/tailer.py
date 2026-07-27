"""Deciding what a file-follower should do next — pure, no IO.

Following a growing log is easy until the writer *rotates* it: many loggers
truncate the file in place, or rename it aside and create a fresh one, at which
point our saved byte offset points into the wrong (or no longer existing) data.
Detecting that is the only subtle part of tailing, and it's plain arithmetic over
`os.stat` results, so it lives here and unit-tests without touching a disk.
"""

from __future__ import annotations

from dataclasses import dataclass

READ = "read"  # the file grew — read from `offset` onward
REWIND = "rewind"  # truncated or replaced — start over from byte 0
IDLE = "idle"  # nothing changed


@dataclass(frozen=True, slots=True)
class TailState:
    """A snapshot of the followed file's identity and size.

    `key` is whatever the OS gives us to tell "same file" apart from "a new file
    with the same name" — the inode on POSIX, and the file index on Windows (or
    the creation time as a fallback). `None` means "couldn't tell", which we treat
    as *not* a change, so an unreliable identity never causes a spurious re-read.
    """

    size: int
    key: object | None = None


def next_action(prev: TailState, cur: TailState) -> str:
    """What to do given the previous and current snapshots.

    Rewind when the file was replaced (different identity) or shrank (truncated in
    place) — in both cases our offset is meaningless. Read when it grew. Otherwise
    idle. Note a rotation that lands on *exactly* the same size is indistinguishable
    by size alone, which is why identity is checked first.
    """
    if prev.key is not None and cur.key is not None and prev.key != cur.key:
        return REWIND
    if cur.size < prev.size:
        return REWIND
    if cur.size > prev.size:
        return READ
    return IDLE


def split_complete_lines(buffer):
    """Split `buffer` into complete lines plus the trailing remainder.

    A writer can flush mid-line, so whatever follows the last newline is not a
    finished log line yet — emitting it would produce a truncated entry and then a
    duplicate when the rest arrives. Return it for the caller to keep buffered.

    Works on `str` or `bytes`: the follower reads **binary** (text-mode `tell()`
    returns an opaque cookie, not a byte offset, which makes offset arithmetic
    meaningless) and decodes per line, so bytes is the real-world case.
    """
    newline = b"\n" if isinstance(buffer, bytes) else "\n"
    if not buffer:
        return [], buffer
    lines = buffer.split(newline)
    remainder = lines.pop()  # empty when the buffer ended exactly on a newline
    return lines, remainder
