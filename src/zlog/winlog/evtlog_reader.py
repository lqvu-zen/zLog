"""Background thread that streams a Windows Event Log channel.

Mirrors `zlog.winlog.dbwin_reader.DebugOutputReader`'s contract: work happens
off the main thread and reaches the UI only via signals (`batch_ready` /
`error`). pywin32 (`win32evtlog`/`win32event`) is imported lazily inside
`run()`, so importing this module is safe on any platform; the pure XML
mapping lives in `zlog.core.winevent`.

Two phases: a one-shot **backfill** of the last `backfill` existing events
(`EvtQuery` in reverse-direction, like logcat's own tail), then a **live
subscription** (`EvtSubscribe` + a signal event) for anything after — the same
poll-with-timeout shape `DebugOutputReader` uses for `WaitForSingleObject`, so
`stop()` is honored within one wait slice instead of blocking on a callback.
"""

from __future__ import annotations

import sys
import time

from PySide6.QtCore import QThread, Signal

from zlog.core.applog import get_logger
from zlog.core.models import LogEntry
from zlog.core.winevent import parse_event_xml

_log = get_logger()

_BACKFILL_DEFAULT = 200
_BATCH_SIZE = 200  # flush to the UI at most this many rows at once
_FLUSH_INTERVAL = 0.2  # ...or this often, whichever comes first (seconds)
_WAIT_MS = 200  # wait slice, so stop() is honored within ~200 ms
_DRAIN_CAP = 200  # events pulled per wake-up of the subscription


def is_supported() -> bool:
    """Event Log capture is Windows-only."""
    return sys.platform == "win32"


def should_flush(batch_len: int, elapsed: float) -> bool:
    """Emit the accumulated batch now (size or time cap). Pure."""
    if batch_len <= 0:
        return False
    return batch_len >= _BATCH_SIZE or elapsed >= _FLUSH_INTERVAL


class EventLogReader(QThread):
    batch_ready = Signal(list)  # list[LogEntry]
    error = Signal(str)

    def __init__(self, channel: str, backfill: int = _BACKFILL_DEFAULT, parent=None):
        super().__init__(parent)
        self.channel = channel
        self.backfill = backfill
        # Not a device stream, but the UI reads `reader.serial` in a few adb
        # paths (process-map refresh, current-serial); "" keeps those no-ops.
        self.serial = ""
        # Set here rather than in run(): stop() can land before the thread body
        # begins (or finishes backfill/subscribe setup), and setting it True
        # there would resurrect a cancelled capture (see ui/file_follower.py's
        # FileFollower for the same fix, and docs/plans/ci-windows-job.md for
        # how this was found — a real race, not just test hygiene).
        self._running = True

    def run(self) -> None:  # pragma: no cover - Windows-only capture loop
        if not is_supported():
            self.error.emit("The Windows Event Log is only available on Windows.")
            return
        try:
            import win32event
            import win32evtlog
        except Exception as exc:
            self.error.emit(f"Event Log capture unavailable: {exc}")
            return

        try:
            backfilled = self._backfill(win32evtlog)
        except Exception as exc:
            _log.exception("Event Log backfill failed: %s", self.channel)
            self.error.emit(f"Could not read the {self.channel} log: {exc}")
            return
        if backfilled:
            self.batch_ready.emit(backfilled)

        try:
            signal_event = win32event.CreateEvent(None, True, False, None)
            subscription = win32evtlog.EvtSubscribe(
                self.channel,
                win32evtlog.EvtSubscribeToFutureEvents,
                SignalEvent=signal_event,
            )
        except Exception as exc:
            self.error.emit(f"Could not subscribe to {self.channel}: {exc}")
            return

        _log.info("Event Log capture started: %s", self.channel)
        batch: list[LogEntry] = []
        last = time.monotonic()
        try:
            while self._running:
                rc = win32event.WaitForSingleObject(signal_event, _WAIT_MS)
                if not self._running:
                    break
                if rc == win32event.WAIT_OBJECT_0:
                    win32event.ResetEvent(signal_event)
                    for handle in self._drain(win32evtlog, subscription):
                        entry = self._render(win32evtlog, handle)
                        if entry is not None:
                            batch.append(entry)
                if should_flush(len(batch), time.monotonic() - last):
                    self.batch_ready.emit(batch)
                    batch = []
                    last = time.monotonic()
        except Exception as exc:
            _log.exception("Event Log capture stopped: %s", self.channel)
            self.error.emit(f"Event Log capture stopped: {exc}")
        finally:
            if batch:
                self.batch_ready.emit(batch)

    def _backfill(self, win32evtlog) -> list[LogEntry]:
        if self.backfill <= 0:
            return []
        flags = win32evtlog.EvtQueryChannelPath | win32evtlog.EvtQueryReverseDirection
        query = win32evtlog.EvtQuery(self.channel, flags)
        handles = self._drain(win32evtlog, query, self.backfill)
        entries = [self._render(win32evtlog, h) for h in reversed(handles)]
        return [e for e in entries if e is not None]

    def _render(self, win32evtlog, handle) -> LogEntry | None:
        try:
            xml_text = win32evtlog.EvtRender(handle, win32evtlog.EvtRenderEventXml)
        except Exception:
            _log.exception("Skipping an unrenderable event on %s", self.channel)
            return None
        return parse_event_xml(xml_text)

    @staticmethod
    def _drain(win32evtlog, handle, cap: int = _DRAIN_CAP) -> list:
        """`EvtNext` raises once nothing more is available — that's the normal
        "caught up" signal, not an error, so it's swallowed into an empty
        drain rather than propagating."""
        try:
            return win32evtlog.EvtNext(handle, cap)
        except Exception:
            return []

    def stop(self) -> None:
        """Called from the UI thread: the ~200 ms wait slice lets the loop
        notice `_running` went False without cross-thread event signaling."""
        self._running = False
        self.wait(2000)
