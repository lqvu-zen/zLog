"""Pure parsing/mapping for Windows `OutputDebugString` capture (DBWIN).

The Windows debug channel publishes each `OutputDebugString` call to a single
shared 4 KB buffer whose layout is a 4-byte little-endian process id followed by
a NUL-terminated ANSI string. The actual buffer/event plumbing is Windows-only
and lives in `zlog.winlog`; everything here is OS-free (no ctypes, no Qt), so the
mapping to `LogEntry` is unit-testable on any platform.
"""

from __future__ import annotations

from datetime import datetime

from zlog.core.models import LogEntry

# Substrings (checked case-insensitively) that bump a level-less debug line to a
# severity, so "show Warning and above" still surfaces app errors. Kept small and
# easy to reason about; the reader can expose a toggle to disable it.
_ERROR_MARKERS = ("error", "exception", "fail", "fatal", "critical")
_WARN_MARKERS = ("warn",)


def parse_dbwin_record(buf: bytes, *, encoding: str = "utf-8") -> tuple[int, str]:
    """Split a raw DBWIN buffer into ``(pid, message)``.

    Layout: a little-endian ``DWORD`` pid, then the message bytes up to the first
    NUL (the rest of the 4 KB buffer is stale padding). A buffer too short to hold
    the pid yields ``(0, "")``. Undecodable bytes are replaced rather than raising,
    and a trailing newline (apps often append one) is stripped. ``mbcs`` is
    deliberately avoided as a default since it doesn't exist off Windows; the
    reader may pass the real ANSI code page.
    """
    if len(buf) < 4:
        return 0, ""
    pid = int.from_bytes(buf[:4], "little")
    raw = buf[4:].split(b"\x00", 1)[0]
    message = raw.decode(encoding, errors="replace").rstrip("\r\n")
    return pid, message


def infer_level(message: str) -> str:
    """Best-effort severity for a debug line that carries none of its own."""
    low = message.lower()
    if any(m in low for m in _ERROR_MARKERS):
        return "E"
    if any(m in low for m in _WARN_MARKERS):
        return "W"
    return "I"


def format_time(when: datetime) -> str:
    """Render a timestamp in logcat's ``MM-DD HH:MM:SS.mmm`` shape (millisecond
    precision), so the existing time column, `since:`/`until:`, and Go-to-time
    keep working for debug-output rows."""
    return when.strftime("%m-%d %H:%M:%S.") + f"{when.microsecond // 1000:03d}"


def build_entry(
    pid: int,
    name: str,
    message: str,
    when: datetime,
    *,
    infer: bool = True,
) -> LogEntry:
    """Map one captured debug line to a `LogEntry`.

    `name` is the resolved process image name (falls back to the pid as the tag so
    tag-based filtering always has something). `OutputDebugString` carries no
    thread id or severity, so `tid` is empty and `level` is inferred (or `I` when
    `infer` is off). `source` is stamped ``"dbwin"`` so a merged tab can tell these
    rows apart from adb ones.
    """
    return LogEntry(
        time=format_time(when),
        pid=str(pid),
        tid="",
        level=infer_level(message) if infer else "I",
        tag=name or str(pid),
        message=message,
        source="dbwin",
    )
