"""Background loader for large `.log` files.

Reading and parsing a big capture on the GUI thread freezes the window. This
`QThread` reads the file line-by-line, parses in batches (like `AdbReader`), and
reaches the UI only via signals — `batch_ready`, `progress`, `done`, `error` —
so `MainWindow` fills the model incrementally with a cancelable progress dialog.
"""

from __future__ import annotations

import os

from PySide6.QtCore import QThread, Signal

from zlog.core.session import iter_entry_batches

_BATCH_SIZE = 50  # small batches keep the UI responsive during a big load


class FileLoader(QThread):
    batch_ready = Signal(list)  # list[LogEntry]
    progress = Signal(int, int)  # bytes_read, total_bytes
    done = Signal(int)  # total lines loaded
    error = Signal(str)

    def __init__(self, path: str, parent=None):
        super().__init__(parent)
        self._path = path
        self._running = False

    def run(self) -> None:
        self._running = True
        try:
            total = os.path.getsize(self._path)
        except OSError:
            total = 0
        read = 0
        lines = 0
        try:
            with open(self._path, encoding="utf-8", errors="replace") as fh:
                # Batch lazily off the file iterator so we never hold the whole file.
                def _counting_lines():
                    nonlocal read, lines
                    for raw in fh:
                        if not self._running:
                            return
                        read += len(raw.encode("utf-8", "replace"))
                        lines += 1
                        yield raw

                for batch in iter_entry_batches(_counting_lines(), _BATCH_SIZE):
                    if not self._running:
                        break
                    self.batch_ready.emit(batch)
                    self.progress.emit(read, total)
        except OSError as exc:
            self.error.emit(str(exc))
            return
        self.done.emit(lines)

    def stop(self) -> None:
        """Ask the loader to abort at the next batch boundary (Cancel)."""
        self._running = False
