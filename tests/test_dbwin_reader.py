"""What's testable of the DBWIN reader off Windows: it imports cleanly, reports
non-Windows gracefully, and its pure helpers are correct. The capture loop itself
is Windows-only and covered manually."""

from __future__ import annotations

import sys

from zlog.winlog.dbwin_reader import is_supported, object_names, should_flush
from zlog.winlog.procnames import ProcessNameCache


def test_module_imports_without_windows(qapp):
    # The import above already proves no Win32 symbols are needed at import time;
    # instantiating the class must likewise not touch ctypes/mmap.
    from zlog.winlog.dbwin_reader import DebugOutputReader

    r = DebugOutputReader()
    assert r.global_capture is False


def test_is_supported_matches_platform():
    assert is_supported() == (sys.platform == "win32")


def test_object_names_local():
    assert object_names(False) == (
        "DBWIN_BUFFER",
        "DBWIN_BUFFER_READY",
        "DBWIN_DATA_READY",
    )


def test_object_names_global_prefixed():
    buf, ready, data = object_names(True)
    assert buf == "Global\\DBWIN_BUFFER"
    assert ready.startswith("Global\\") and data.startswith("Global\\")


def test_should_flush_rules():
    assert should_flush(0, 999) is False  # nothing pending
    assert should_flush(1, 0.0) is False  # below both caps
    assert should_flush(1, 0.2) is True  # time cap
    assert should_flush(500, 0.0) is True  # size cap


def test_procname_cache_returns_empty_off_windows():
    cache = ProcessNameCache()
    if sys.platform != "win32":
        assert cache.name_for(4321) == ""
        assert cache.name_for(4321) == ""  # cached, still fine
