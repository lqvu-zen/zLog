"""Follow a growing log file and stream new lines into the view (tail -f).

Like :class:`~zlog.ui.file_loader.FileLoader`, but it doesn't stop at EOF: it
reads what's there, then polls for growth. Cross-platform (a small `os.stat`
poll rather than an OS watch API), so it works the same on Windows and Linux and
is genuinely testable in CI.

Same contract as every other source — the blocking work happens on this thread and
reaches the UI only through signals — so it attaches via `CaptureController` and
Stop tears it down like a device stream.
"""

from __future__ import annotations

import os
import time

from PySide6.QtCore import QThread, Signal

from zlog.core.applog import get_logger
from zlog.core.logformat import CompiledFormat
from zlog.core.models import LogEntry
from zlog.core.parser import parse_line
from zlog.core.tailer import READ, REWIND, TailState, next_action, split_complete_lines

_log = get_logger()

_POLL_INTERVAL = 0.25  # seconds between stat() checks; bounds stop() latency too
_BATCH_SIZE = 500
_FLUSH_INTERVAL = 0.1
_CHUNK = 65536


def should_flush(batch_len: int, elapsed: float) -> bool:
    """Emit the accumulated batch now (size or time cap). Pure."""
    if batch_len <= 0:
        return False
    return batch_len >= _BATCH_SIZE or elapsed >= _FLUSH_INTERVAL


def file_key(path: str):
    """An identity for the file at `path`, to tell a rotation from plain growth.

    Inode + device is the identity on POSIX. `st_ctime` must **not** be folded in
    there: on POSIX it's the inode *change* time, which ticks on every append, so
    including it would make every write look like a rotation and re-read the file
    from the start. On Windows `st_ctime` really is creation time and usefully
    guards against a reused file index, so it's included only there.

    Any failure yields None, which `next_action` treats as "can't tell" rather
    than "changed".
    """
    try:
        st = os.stat(path)
    except OSError:
        return None
    if os.name == "nt":
        return (st.st_ino, st.st_dev, st.st_ctime)
    return (st.st_ino, st.st_dev)


class FileFollower(QThread):
    batch_ready = Signal(list)  # list[LogEntry]
    error = Signal(str)
    stream_ended = Signal()

    def __init__(
        self,
        path: str,
        from_end: bool = False,
        formats: list[CompiledFormat] | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self.path = path
        self.from_end = from_end  # skip existing content, show only new lines
        self.serial = ""  # not a device; keeps adb-oriented UI paths safe
        # Read-only snapshot handed in at construction, same rule as AdbReader —
        # a running reader never reaches back for "the current format".
        self.formats = formats
        # Set here rather than in run(): stop() can land before the thread body
        # begins, and setting it True there would resurrect a cancelled follow.
        self._running = True
        self._partial = b""  # bytes after the last newline: not a finished line yet

    @property
    def name(self) -> str:
        return os.path.basename(self.path)

    def run(self) -> None:
        try:
            size = os.path.getsize(self.path)
        except OSError as exc:
            self.error.emit(f"Could not open {self.name}: {exc}")
            return
        offset = size if self.from_end else 0
        state = TailState(size=size, key=file_key(self.path))
        _log.info("Following %s (from_end=%s)", self.path, self.from_end)

        batch: list[LogEntry] = []
        last = time.monotonic()
        try:
            if not self.from_end:
                offset = self._read_from(offset, batch)
            while self._running:
                if should_flush(len(batch), time.monotonic() - last):
                    self.batch_ready.emit(batch)
                    batch = []
                    last = time.monotonic()
                time.sleep(_POLL_INTERVAL)
                if not self._running:
                    break
                try:
                    cur = TailState(size=os.path.getsize(self.path), key=file_key(self.path))
                except OSError as exc:
                    # Deleted or locked mid-follow: report, keep what we captured.
                    self.error.emit(f"Stopped following {self.name}: {exc}")
                    break
                # Compare against how far we've actually read, not the previous
                # size: if the file is now shorter than what we consumed, it was
                # truncated, which is the reliable signal. (An in-place rewrite
                # that lands on exactly the same size with the same inode is
                # undetectable without hashing — `tail -f` has the same blind spot.)
                action = next_action(TailState(size=offset, key=state.key), cur)
                if action == REWIND:
                    offset, self._partial = 0, b""
                    offset = self._read_from(offset, batch)
                elif action == READ:
                    offset = self._read_from(offset, batch)
                state = TailState(size=cur.size, key=cur.key)
        except Exception as exc:  # a dead thread would otherwise fail silently
            _log.exception("File follow stopped")
            self.error.emit(f"Stopped following {self.name}: {exc}")
        finally:
            if batch:
                self.batch_ready.emit(batch)
            if self._running:
                self.stream_ended.emit()

    def _read_from(self, offset: int, batch: list[LogEntry]) -> int:
        """Read from byte `offset` to EOF, appending parsed entries to `batch`.

        Returns the new byte offset. Reads **binary** and decodes per complete
        line: text mode's `tell()` is an opaque cookie rather than a byte count,
        and decoding a chunk that splits a multi-byte character would corrupt it.
        A trailing partial line is held back until its newline arrives, so a
        mid-flush write never yields a truncated entry followed by a duplicate.
        """
        with open(self.path, "rb") as fh:
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
