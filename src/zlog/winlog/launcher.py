"""Launch an app from zLog and stream its console output into the log view.

Cross-platform on purpose (stdlib ``subprocess``): capturing a child's
stdout/stderr works anywhere, and on Windows the app's ``OutputDebugString``
tracing is picked up in parallel by :class:`~zlog.winlog.dbwin_reader.DebugOutputReader`.
Launching is what lets you see an app from its very first line, which attaching to
an already-running process can't do.

Same contract as :class:`~zlog.adb.reader.AdbReader`: the blocking read loop runs
on this thread and reaches the UI only through signals.
"""

from __future__ import annotations

import os
import subprocess
import time
from datetime import datetime

from PySide6.QtCore import QThread, Signal

from zlog.core.applog import get_logger
from zlog.core.dbwin import format_time, infer_level
from zlog.core.models import LogEntry

_log = get_logger()

_BATCH_SIZE = 500
_FLUSH_INTERVAL = 0.1  # seconds


def should_flush(batch_len: int, elapsed: float) -> bool:
    """Emit the accumulated batch now (size or time cap). Pure."""
    if batch_len <= 0:
        return False
    return batch_len >= _BATCH_SIZE or elapsed >= _FLUSH_INTERVAL


def build_argv(exe: str, arguments: str = "") -> list[str]:
    """Build the child's argv. Kept a **list** (never a joined string) so paths and
    arguments containing spaces survive; `arguments` is split shell-style. Pure."""
    import shlex

    argv = [exe]
    if arguments.strip():
        # posix=False keeps Windows backslashes in paths from being eaten.
        argv += shlex.split(arguments, posix=(os.name != "nt"))
    return argv


class LaunchReader(QThread):
    batch_ready = Signal(list)  # list[LogEntry]
    error = Signal(str)
    stream_ended = Signal()  # the child exited on its own (not stop())

    def __init__(self, argv: list[str], cwd: str | None = None, parent=None):
        super().__init__(parent)
        self.argv = list(argv)
        self.cwd = cwd or None
        self.serial = ""  # not a device; keeps adb-oriented UI paths safe
        self.pid = 0  # the child's pid, once started (used to focus the query)
        self._proc: subprocess.Popen | None = None
        # Set here rather than in run(): stop() can land before the thread body
        # begins, and setting it True there would resurrect a cancelled launch
        # (see ui/file_follower.py's FileFollower for the same fix, and
        # docs/plans/ci-windows-job.md for how this class of race was found).
        self._running = True

    @property
    def app_name(self) -> str:
        """Base name of the launched executable — the tag/tab label."""
        return os.path.basename(self.argv[0]) if self.argv else ""

    def run(self) -> None:
        try:
            self._proc = subprocess.Popen(
                self.argv,
                cwd=self.cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,  # interleave stderr into one stream
                encoding="utf-8",
                errors="replace",  # a stray byte must not kill the thread
                bufsize=1,  # line-buffered
            )
        except OSError as exc:
            _log.error("Launch failed: %r (%s)", self.argv, exc)
            self.error.emit(f"Could not launch {self.app_name or 'app'}: {exc}")
            return
        self.pid = self._proc.pid
        name = self.app_name
        _log.info("Launched %s (pid=%s): %r", name, self.pid, self.argv)

        assert self._proc.stdout is not None
        batch: list[LogEntry] = []
        last = time.monotonic()
        try:
            for raw in self._proc.stdout:
                if not self._running:
                    break
                batch.append(self._entry(raw.rstrip("\r\n"), name))
                if should_flush(len(batch), time.monotonic() - last):
                    self.batch_ready.emit(batch)
                    batch = []
                    last = time.monotonic()
        except Exception as exc:  # a dead reader thread would fail silently
            _log.exception("Launched-app capture stopped")
            if batch:
                self.batch_ready.emit(batch)
            self.error.emit(f"Capture stopped: {exc}")
            return
        if batch:
            self.batch_ready.emit(batch)
        if self._running:
            self.stream_ended.emit()  # the app exited by itself

    def _entry(self, text: str, name: str) -> LogEntry:
        return LogEntry(
            time=format_time(datetime.now()),
            pid=str(self.pid),
            tid="",
            level=infer_level(text),
            tag=name,
            message=text,
            source="stdout",
        )

    def stop(self) -> None:
        """Called from the UI thread: end capture and terminate the child (no
        orphans). Terminating also unblocks the blocking pipe read."""
        self._running = False
        if self._proc and self._proc.poll() is None:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self._proc.kill()  # last resort
        self.wait(2000)
