"""Accept a newline-delimited text stream over TCP and feed it into the log
view — any process that can open a socket becomes a log source, with no adb
and no file. See docs/plans/network-log-source.md.

Same contract as every other reader: the blocking work (`select`/`accept`/
`recv`) happens on this thread and reaches the UI only through signals.
"""

from __future__ import annotations

import select
import socket
import time

from PySide6.QtCore import QThread, Signal

from zlog.core.applog import get_logger
from zlog.core.logformat import CompiledFormat
from zlog.core.models import LogEntry
from zlog.core.parser import parse_line
from zlog.core.tailer import split_complete_lines

_log = get_logger()

_BATCH_SIZE = 500
_FLUSH_INTERVAL = 0.1  # seconds
_POLL_INTERVAL = 0.25  # select() timeout; bounds stop() latency
# Guards a sender that never terminates a line: without this, a broken/hostile
# client could grow `_partial` without bound. No existing source needs this —
# files and adb both terminate lines reliably.
_MAX_PARTIAL_LINE = 1_000_000


def should_flush(batch_len: int, elapsed: float) -> bool:
    """Emit the accumulated batch now (size or time cap). Pure."""
    if batch_len <= 0:
        return False
    return batch_len >= _BATCH_SIZE or elapsed >= _FLUSH_INTERVAL


class NetworkReader(QThread):
    batch_ready = Signal(list)  # list[LogEntry]
    error = Signal(str)
    stream_ended = Signal()
    listening = Signal(int)  # the actual bound port (resolves port=0 -> ephemeral)

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 0,
        formats: list[CompiledFormat] | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self.host = host
        self.port = port
        self.formats = formats
        self.serial = ""  # not a device; keeps adb-oriented UI paths safe
        # Set here rather than in run(): stop() can land before the thread body
        # begins, and setting it True there would resurrect a cancelled listen
        # (same fix as ui/file_follower.py's FileFollower).
        self._running = True
        self._server: socket.socket | None = None
        self._partial = b""

    @property
    def name(self) -> str:
        return f"{self.host}:{self.port}"

    def run(self) -> None:
        try:
            server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server.bind((self.host, self.port))
            # A backlog bigger than "1 active sender" on purpose: a second
            # connection attempt must be *our* application-level reject (with a
            # message the sender can at least have the socket closed on),
            # not an OS-level connection refusal racing against how fast the
            # accept loop gets to it.
            server.listen(5)
            server.setblocking(False)
        except OSError as exc:
            self.error.emit(f"Could not listen on {self.host}:{self.port}: {exc}")
            return
        self._server = server
        self.port = server.getsockname()[1]
        _log.info("Listening on %s:%s", self.host, self.port)
        self.listening.emit(self.port)

        conn: socket.socket | None = None
        batch: list[LogEntry] = []
        last_flush = time.monotonic()
        try:
            while self._running:
                if should_flush(len(batch), time.monotonic() - last_flush):
                    self.batch_ready.emit(batch)
                    batch = []
                    last_flush = time.monotonic()
                readers = [server] if conn is None else [server, conn]
                try:
                    ready, _, _ = select.select(readers, [], [], _POLL_INTERVAL)
                except OSError:
                    break  # a socket was closed under us (stop())
                if server in ready:
                    new_conn, addr = server.accept()
                    if conn is None:
                        conn = new_conn
                        conn.setblocking(False)
                        _log.info("Connection from %s", addr)
                    else:
                        # Already serving one sender: reject rather than queue
                        # or merge (see the plan's "one connection at a time").
                        new_conn.close()
                        self.error.emit(
                            f"Rejected a second connection from {addr[0]}:{addr[1]} — "
                            "already connected to one sender."
                        )
                if conn is not None and conn in ready:
                    try:
                        chunk = conn.recv(65536)
                    except OSError:
                        chunk = b""
                    if not chunk:
                        _log.info("Sender disconnected")
                        conn.close()
                        conn = None
                        self._partial = b""
                    else:
                        lines, self._partial = split_complete_lines(self._partial + chunk)
                        if len(self._partial) > _MAX_PARTIAL_LINE:
                            _log.warning(
                                "Dropping oversized unterminated line (%d bytes)",
                                len(self._partial),
                            )
                            self._partial = b""
                        batch.extend(
                            parse_line(
                                raw.decode("utf-8", errors="replace").rstrip("\r"), self.formats
                            )
                            for raw in lines
                        )
        except Exception as exc:  # a dead thread would otherwise fail silently
            _log.exception("Network listener stopped")
            self.error.emit(f"Stopped listening: {exc}")
        finally:
            if batch:
                self.batch_ready.emit(batch)
            if conn is not None:
                conn.close()
            try:
                server.close()
            except OSError:
                pass
            if self._running:
                self.stream_ended.emit()

    def stop(self) -> None:
        """End listening; the select() timeout bounds how long this takes."""
        self._running = False
        self.wait(3000)
