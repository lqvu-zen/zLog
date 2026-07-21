"""Background thread that streams `adb logcat` into the app.

Why a thread? `adb logcat` streams forever. Reading it on the GUI thread would
freeze the window, so the read loop lives here, off the main thread, and we
touch the UI only by emitting signals (Qt delivers them safely to the main
thread).
"""

from __future__ import annotations

import dataclasses
import subprocess
import time

from PySide6.QtCore import QThread, Signal

from zlog.core.applog import get_logger
from zlog.core.models import LogEntry
from zlog.core.parser import parse_line

_log = get_logger()

# Flush to the UI in chunks rather than one signal per line, so a busy log doesn't
# drown the event loop. On Start, adb dumps the whole on-device buffer as fast as it
# can; emitting a cross-thread signal every 50 lines floods the event loop (the window
# goes "Not Responding"). So we emit at most every _BATCH_SIZE lines OR every
# _FLUSH_INTERVAL seconds — far fewer signals during a burst, low latency when live.
_BATCH_SIZE = 2000
_FLUSH_INTERVAL = 0.1  # seconds


def should_flush(batch_len: int, elapsed: float) -> bool:
    """Whether to emit the accumulated batch now (size cap or time cap). Pure."""
    if batch_len <= 0:
        return False
    return batch_len >= _BATCH_SIZE or elapsed >= _FLUSH_INTERVAL


# Buffers `adb logcat -b` accepts; anything else is ignored so a bad value can't
# break the command. An empty selection uses adb's default buffers.
_VALID_BUFFERS = ("main", "system", "crash", "radio", "events", "kernel")


def build_logcat_command(adb_path, serial, buffers=None, tail=0, since_time=None):
    """Build the `adb logcat` argv. Pure (no Qt), so it's unit-testable.

    `since_time` (a logcat timestamp like "06-30 12:34:56.789") wins over `tail`
    and maps to `-T <time>` — used on auto-reconnect to resume near where the
    stream dropped instead of re-dumping the whole on-device buffer.
    """
    cmd = [adb_path]
    if serial:
        cmd += ["-s", serial]
    cmd += ["logcat", "-v", "threadtime"]
    for buf in buffers or []:
        if buf in _VALID_BUFFERS:
            cmd += ["-b", buf]
    if since_time:
        cmd += ["-T", since_time]  # print from this timestamp onward, then follow
    elif tail and tail > 0:
        cmd += ["-T", str(int(tail))]  # print the last N lines, then keep following
    return cmd


class AdbReader(QThread):
    batch_ready = Signal(list)  # list[LogEntry]
    error = Signal(str)
    stream_ended = Signal()  # the process ended on its own (device drop), not stop()

    def __init__(
        self,
        serial: str | None = None,
        adb_path: str = "adb",
        buffers: list[str] | None = None,
        tail: int = 0,
        since_time: str | None = None,
        source: str = "",
        parent=None,
    ):
        super().__init__(parent)
        # serial selects a specific device (`adb -s <serial>`); None uses the
        # single default device, matching adb's own behavior.
        self.serial = serial
        self.adb_path = adb_path
        self.buffers = buffers
        self.tail = tail
        self.since_time = since_time
        # In a merged multi-device view, each reader stamps its lines with this
        # label (the device serial) so the model can tell sources apart.
        self.source = source
        self._proc: subprocess.Popen | None = None
        self._running = False

    def _command(self) -> list[str]:
        return build_logcat_command(
            self.adb_path, self.serial, self.buffers, self.tail, self.since_time
        )

    def run(self) -> None:
        """Runs on the background thread once start() is called."""
        self._running = True
        try:
            self._proc = subprocess.Popen(
                self._command(),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                # Logcat output is UTF-8 and can contain non-ASCII app messages;
                # pin the codec instead of inheriting the platform's default text
                # encoding (cp1252 on Windows), and replace anything undecodable
                # rather than raising, so a stray byte can't kill the thread.
                encoding="utf-8",
                errors="replace",
                bufsize=1,  # line-buffered
            )
        except FileNotFoundError:
            _log.error("adb not found: %r (command=%r)", self.adb_path, self._command())
            self.error.emit(
                f"Could not find '{self.adb_path}'. Install Android "
                "platform-tools and make sure adb is on your PATH."
            )
            return
        _log.info("logcat started: %s", " ".join(self._command()))

        assert self._proc.stdout is not None
        batch: list[LogEntry] = []
        last = time.monotonic()
        try:
            for raw in self._proc.stdout:
                if not self._running:
                    break
                entry = parse_line(raw.rstrip("\n"))
                if self.source:
                    entry = dataclasses.replace(entry, source=self.source)
                batch.append(entry)
                if should_flush(len(batch), time.monotonic() - last):
                    self.batch_ready.emit(batch)
                    batch = []
                    last = time.monotonic()
        except Exception as exc:  # a dead reader thread fails silently otherwise
            _log.exception("Log reading stopped")
            if batch:
                self.batch_ready.emit(batch)
            self.error.emit(f"Log reading stopped: {exc}")
            return
        if batch:
            self.batch_ready.emit(batch)
        if self._running:
            # We didn't call stop(), yet the process ended — the device dropped
            # (unplugged / adb died). Tell the UI so it can try to reconnect.
            self.stream_ended.emit()

    def stop(self) -> None:
        """Called from the UI thread to end streaming."""
        self._running = False
        if self._proc:
            self._proc.terminate()
        self.wait(2000)
