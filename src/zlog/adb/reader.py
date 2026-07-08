"""Background thread that streams `adb logcat` into the app.

Why a thread? `adb logcat` streams forever. Reading it on the GUI thread would
freeze the window, so the read loop lives here, off the main thread, and we
touch the UI only by emitting signals (Qt delivers them safely to the main
thread).
"""

from __future__ import annotations

import subprocess

from PySide6.QtCore import QThread, Signal

from zlog.core.models import LogEntry
from zlog.core.parser import parse_line

# Flush to the UI in chunks rather than one signal per line, so a busy log
# doesn't drown the event loop. Tune for responsiveness vs. overhead.
_BATCH_SIZE = 50


class AdbReader(QThread):
    batch_ready = Signal(list)  # list[LogEntry]
    error = Signal(str)

    def __init__(self, serial: str | None = None, adb_path: str = "adb", parent=None):
        super().__init__(parent)
        # serial selects a specific device (`adb -s <serial>`); None uses the
        # single default device, matching adb's own behavior.
        self.serial = serial
        self.adb_path = adb_path
        self._proc: subprocess.Popen | None = None
        self._running = False

    def _command(self) -> list[str]:
        cmd = [self.adb_path]
        if self.serial:
            cmd += ["-s", self.serial]
        cmd += ["logcat", "-v", "threadtime"]
        return cmd

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
            self.error.emit(
                f"Could not find '{self.adb_path}'. Install Android "
                "platform-tools and make sure adb is on your PATH."
            )
            return

        assert self._proc.stdout is not None
        batch: list[LogEntry] = []
        try:
            for raw in self._proc.stdout:
                if not self._running:
                    break
                batch.append(parse_line(raw.rstrip("\n")))
                if len(batch) >= _BATCH_SIZE:
                    self.batch_ready.emit(batch)
                    batch = []
        except Exception as exc:  # a dead reader thread fails silently otherwise
            if batch:
                self.batch_ready.emit(batch)
            self.error.emit(f"Log reading stopped: {exc}")
            return
        if batch:
            self.batch_ready.emit(batch)

    def stop(self) -> None:
        """Called from the UI thread to end streaming."""
        self._running = False
        if self._proc:
            self._proc.terminate()
        self.wait(2000)
