"""Background thread that captures ``OutputDebugString`` output (the DBWIN buffer).

Mirrors :class:`zlog.adb.reader.AdbReader`'s contract — work happens off the main
thread and reaches the UI only via signals (``batch_ready`` / ``error``). All
Win32 access (ctypes + the named shared mapping) is imported lazily inside
``run()``, so importing this module is safe on any platform; the pure buffer
parsing lives in :mod:`zlog.core.dbwin`.

Protocol (same as Sysinternals DebugView): the capturer owns a 4 KB section
``DBWIN_BUFFER`` plus two auto-reset events. ``DBWIN_BUFFER_READY`` starts
signaled; a writer waits on it, writes ``<pid><message>`` and signals
``DBWIN_DATA_READY``; we wait on that, read the record, then re-signal
``DBWIN_BUFFER_READY``. Only one capturer can own the buffer at a time.
"""

from __future__ import annotations

import sys
import time
from datetime import datetime

from PySide6.QtCore import QThread, Signal

from zlog.core.applog import get_logger
from zlog.core.dbwin import build_entry, parse_dbwin_record
from zlog.core.models import LogEntry
from zlog.winlog.procnames import ProcessNameCache

_log = get_logger()

_BUF_SIZE = 4096  # the DBWIN section is a fixed 4 KB
_BATCH_SIZE = 500  # flush to the UI at most this many rows at once
_FLUSH_INTERVAL = 0.1  # ...or this often, whichever comes first (seconds)
_WAIT_MS = 200  # WaitForSingleObject slice, so stop() is honored within ~200 ms
_ERROR_ALREADY_EXISTS = 183
_WAIT_OBJECT_0 = 0
_WAIT_TIMEOUT = 0x102


def is_supported() -> bool:
    """DBWIN capture is Windows-only."""
    return sys.platform == "win32"


def object_names(global_capture: bool) -> tuple[str, str, str]:
    """The (buffer, buffer-ready, data-ready) kernel-object names. Global capture
    (services / session 0) prefixes ``Global\\`` and needs elevation. Pure."""
    prefix = "Global\\" if global_capture else ""
    return (
        f"{prefix}DBWIN_BUFFER",
        f"{prefix}DBWIN_BUFFER_READY",
        f"{prefix}DBWIN_DATA_READY",
    )


def should_flush(batch_len: int, elapsed: float) -> bool:
    """Emit the accumulated batch now (size or time cap). Pure."""
    if batch_len <= 0:
        return False
    return batch_len >= _BATCH_SIZE or elapsed >= _FLUSH_INTERVAL


class DebugOutputReader(QThread):
    batch_ready = Signal(list)  # list[LogEntry]
    error = Signal(str)

    def __init__(self, global_capture: bool = False, parent=None):
        super().__init__(parent)
        self.global_capture = global_capture
        self._running = False
        self._names = ProcessNameCache()

    def run(self) -> None:  # pragma: no cover - Windows-only capture loop
        if not is_supported():
            self.error.emit("Capturing debug output is only available on Windows.")
            return
        try:
            import ctypes
            import mmap
            from ctypes import wintypes
        except Exception as exc:
            self.error.emit(f"Debug-output capture unavailable: {exc}")
            return

        kernel32 = ctypes.windll.kernel32
        kernel32.CreateEventW.restype = wintypes.HANDLE
        buf_name, ready_name, data_name = object_names(self.global_capture)

        # Auto-reset events; BUFFER_READY starts signaled so a writer can proceed.
        buffer_ready = kernel32.CreateEventW(None, False, True, ready_name)
        contended = kernel32.GetLastError() == _ERROR_ALREADY_EXISTS
        data_ready = kernel32.CreateEventW(None, False, False, data_name)
        contended = contended or kernel32.GetLastError() == _ERROR_ALREADY_EXISTS
        if contended:
            self.error.emit(
                "Another debug-output capturer (e.g. DebugView) or a debugger is "
                "already running. Close it and try again."
            )
            self._close(kernel32, buffer_ready, data_ready)
            return
        try:
            mm = mmap.mmap(-1, _BUF_SIZE, tagname=buf_name, access=mmap.ACCESS_WRITE)
        except OSError as exc:
            self.error.emit(f"Could not open the debug-output buffer: {exc}")
            self._close(kernel32, buffer_ready, data_ready)
            return

        _log.info("DBWIN capture started (global=%s)", self.global_capture)
        self._running = True
        batch: list[LogEntry] = []
        last = time.monotonic()
        try:
            while self._running:
                rc = kernel32.WaitForSingleObject(data_ready, _WAIT_MS)
                if not self._running:
                    break
                if rc == _WAIT_OBJECT_0:
                    record = bytes(mm[:_BUF_SIZE])
                    pid, message = parse_dbwin_record(record)
                    name = self._names.name_for(pid)
                    batch.append(build_entry(pid, name, message, datetime.now()))
                    kernel32.SetEvent(buffer_ready)  # let the next writer proceed
                elif rc != _WAIT_TIMEOUT:
                    self.error.emit("Debug-output wait failed; stopping capture.")
                    break
                if should_flush(len(batch), time.monotonic() - last):
                    self.batch_ready.emit(batch)
                    batch = []
                    last = time.monotonic()
        except Exception as exc:
            _log.exception("DBWIN capture stopped")
            self.error.emit(f"Debug-output capture stopped: {exc}")
        finally:
            if batch:
                self.batch_ready.emit(batch)
            mm.close()
            self._close(kernel32, buffer_ready, data_ready)

    @staticmethod
    def _close(kernel32, *handles) -> None:  # pragma: no cover - Windows-only
        for h in handles:
            if h:
                kernel32.CloseHandle(h)

    def stop(self) -> None:
        """End capture from the UI thread; the ~200 ms wait slice lets the loop
        notice `_running` went False without cross-thread event signaling."""
        self._running = False
        self.wait(2000)
