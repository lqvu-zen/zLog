"""Follow the newest file in a directory matching a glob pattern (`tail -f` a
rotating log directory) — see docs/plans/directory-glob-follow.md.

For apps that rotate logs by filename (a fresh file per run/day), complementing
`FileFollower`, which handles a single fixed path rotating by inode/truncation.

Reimplements the read/poll loop rather than wrapping a `FileFollower` instance:
a `FileFollower` constructed on this thread would have its signals connected
across threads with no event loop on this thread to deliver them through (this
thread's `run()` is a plain `while` loop, not `self.exec()`). Every signal here
reaches the UI directly instead — the same contract as every other reader.
"""

from __future__ import annotations

import os
import time

from PySide6.QtCore import QThread, Signal

from zlog.core.applog import get_logger
from zlog.core.dirfollow import pick_newest, should_switch
from zlog.core.logformat import CompiledFormat
from zlog.core.models import LogEntry
from zlog.core.parser import parse_line
from zlog.core.tailer import READ, REWIND, TailState, next_action, split_complete_lines
from zlog.ui.file_follower import file_key, should_flush

_log = get_logger()

_POLL_INTERVAL = 0.25  # matches FileFollower's own poll cadence
_SWITCH_GRACE = 2 * _POLL_INTERVAL  # old file must be stable this long before swapping
_CHUNK = 65536
# Batch size/flush interval are `ui.file_follower.should_flush`'s own module
# constants (reused below), not redefined here.


class DirFollower(QThread):
    batch_ready = Signal(list)  # list[LogEntry]
    error = Signal(str)
    stream_ended = Signal()
    switched = Signal(str)  # the new file's basename, for a status-bar note

    def __init__(
        self,
        dir_path: str,
        pattern: str,
        formats: list[CompiledFormat] | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self.dir_path = dir_path
        self.pattern = pattern
        self.formats = formats
        self.serial = ""  # not a device; keeps adb-oriented UI paths safe
        # Set here rather than in run(): stop() can land before the thread body
        # begins, and setting it True there would resurrect a cancelled follow
        # (same fix as ui/file_follower.py's FileFollower).
        self._running = True
        self._partial = b""  # bytes after the last newline: not a finished line yet
        self.current_path: str | None = None  # the file actually being followed right now

    @property
    def name(self) -> str:
        return self.pattern

    def run(self) -> None:
        path = pick_newest(self.dir_path, self.pattern)
        if path is None:
            self.error.emit(f"No files match {self.pattern!r} in {self.dir_path}")
            return
        self.current_path = path
        _log.info("Following folder %s (pattern=%r) -> %s", self.dir_path, self.pattern, path)

        offset = 0
        key = file_key(path)
        last_size = 0
        stable_since = time.monotonic()

        batch: list[LogEntry] = []
        last_flush = time.monotonic()
        try:
            offset = self._read_from(path, offset, batch)
            last_size = offset
            while self._running:
                if should_flush(len(batch), time.monotonic() - last_flush):
                    self.batch_ready.emit(batch)
                    batch = []
                    last_flush = time.monotonic()
                time.sleep(_POLL_INTERVAL)
                if not self._running:
                    break
                try:
                    cur = TailState(size=os.path.getsize(path), key=file_key(path))
                except OSError as exc:
                    # Deleted or locked mid-follow: report, keep what we captured.
                    self.error.emit(f"Stopped following {self.name}: {exc}")
                    break
                if cur.size != last_size:
                    last_size = cur.size
                    stable_since = time.monotonic()
                action = next_action(TailState(size=offset, key=key), cur)
                if action == REWIND:
                    offset, self._partial = 0, b""
                    offset = self._read_from(path, offset, batch)
                elif action == READ:
                    offset = self._read_from(path, offset, batch)
                key = cur.key

                candidate = pick_newest(self.dir_path, self.pattern)
                stable_for = time.monotonic() - stable_since
                if (
                    candidate is not None
                    and candidate != path
                    and should_switch(stable_for, _SWITCH_GRACE)
                ):
                    path = candidate
                    self._partial = b""
                    offset = self._read_from(path, 0, batch)
                    key = file_key(path)
                    last_size = offset
                    stable_since = time.monotonic()
                    self.current_path = path
                    _log.info("Switched to newer file: %s", path)
                    self.switched.emit(os.path.basename(path))
        except Exception as exc:  # a dead thread would otherwise fail silently
            _log.exception("Folder follow stopped")
            self.error.emit(f"Stopped following {self.name}: {exc}")
        finally:
            if batch:
                self.batch_ready.emit(batch)
            if self._running:
                self.stream_ended.emit()

    def _read_from(self, path: str, offset: int, batch: list[LogEntry]) -> int:
        """Same shape as `FileFollower._read_from`, generalized to a `path`
        argument since the followed file can change mid-run."""
        with open(path, "rb") as fh:
            fh.seek(offset)
            while True:
                chunk = fh.read(_CHUNK)
                if not chunk:
                    break
                lines, self._partial = split_complete_lines(self._partial + chunk)
                batch.extend(
                    parse_line(raw.decode("utf-8", errors="replace").rstrip("\r"), self.formats)
                    for raw in lines
                )
            return fh.tell()

    def stop(self) -> None:
        """End following; the poll sleep bounds how long this takes."""
        self._running = False
        self.wait(3000)
