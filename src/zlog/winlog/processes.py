"""Enumerate running processes for the "focus one app" picker (Windows-only).

Uses the Toolhelp snapshot API via ctypes — no dependency — and is imported
lazily/guarded, so this module is importable anywhere and simply returns an empty
list off Windows. The pure shaping (sort/filter/focus) lives in
:mod:`zlog.core.procinfo`.
"""

from __future__ import annotations

import sys

from zlog.core.procinfo import ProcessInfo, sort_processes

TH32CS_SNAPPROCESS = 0x00000002
_INVALID_HANDLE_VALUE = -1
_MAX_PATH = 260


def list_processes() -> list[ProcessInfo]:
    """Every visible running process, sorted for display. ``[]`` off Windows or if
    the snapshot fails (the picker then shows its empty state)."""
    if sys.platform != "win32":
        return []
    try:
        return sort_processes(_snapshot())
    except Exception:  # pragma: no cover - defensive; never break the picker
        return []


def _snapshot() -> list[ProcessInfo]:  # pragma: no cover - Windows-only
    import ctypes
    from ctypes import wintypes

    class PROCESSENTRY32(ctypes.Structure):
        _fields_ = [
            ("dwSize", wintypes.DWORD),
            ("cntUsage", wintypes.DWORD),
            ("th32ProcessID", wintypes.DWORD),
            ("th32DefaultHeapID", ctypes.POINTER(ctypes.c_ulong)),
            ("th32ModuleID", wintypes.DWORD),
            ("cntThreads", wintypes.DWORD),
            ("th32ParentProcessID", wintypes.DWORD),
            ("pcPriClassBase", ctypes.c_long),
            ("dwFlags", wintypes.DWORD),
            ("szExeFile", ctypes.c_char * _MAX_PATH),
        ]

    kernel32 = ctypes.windll.kernel32
    snap = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if snap == _INVALID_HANDLE_VALUE:
        return []
    procs: list[ProcessInfo] = []
    try:
        entry = PROCESSENTRY32()
        entry.dwSize = ctypes.sizeof(PROCESSENTRY32)
        ok = kernel32.Process32First(snap, ctypes.byref(entry))
        while ok:
            name = entry.szExeFile.decode("mbcs", errors="replace")
            procs.append(ProcessInfo(int(entry.th32ProcessID), name))
            ok = kernel32.Process32Next(snap, ctypes.byref(entry))
    finally:
        kernel32.CloseHandle(snap)
    return procs
