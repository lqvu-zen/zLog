"""PID -> process image name for DBWIN rows (Windows-only, best-effort).

`OutputDebugString` gives only a pid; the friendly tag is the process's image
name. Resolving it needs Win32, so everything here is imported lazily and guarded
— on non-Windows (and on any failure: the pid may have already exited or be
protected) the resolver returns "" and the caller falls back to the raw pid.
"""

from __future__ import annotations

import sys


class ProcessNameCache:
    """Small pid -> image-name cache. pids get reused, but a live capture resolves
    a name the moment a pid first appears, which is the common case; a stale hit is
    a cosmetic tag, not a correctness issue."""

    def __init__(self) -> None:
        self._cache: dict[int, str] = {}

    def name_for(self, pid: int) -> str:
        if pid in self._cache:
            return self._cache[pid]
        name = _query_image_name(pid) if sys.platform == "win32" else ""
        self._cache[pid] = name
        return name


def _query_image_name(pid: int) -> str:  # pragma: no cover - Windows-only
    """Return the base image name for `pid` (e.g. ``myapp.exe``) or ""."""
    import ctypes
    from ctypes import wintypes

    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    kernel32 = ctypes.windll.kernel32
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        return ""
    try:
        buf = ctypes.create_unicode_buffer(32768)
        size = wintypes.DWORD(len(buf))
        # QueryFullProcessImageNameW(handle, 0, buf, &size)
        if not kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)):
            return ""
        full = buf.value
    finally:
        kernel32.CloseHandle(handle)
    # Base name only, to keep the tag short (like adb's process names).
    return full.replace("/", "\\").rsplit("\\", 1)[-1]
