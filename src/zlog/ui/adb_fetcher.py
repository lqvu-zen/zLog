"""Background download of platform-tools (see docs/plans/bundle-adb.md).

Same signal discipline as every other reader (AdbReader, DebugOutputReader):
runs entirely off the main thread and reaches the UI only via signals. The
integrity check (verify_download) is the load-bearing step — we're fetching an
executable and running it, so a failed/tampered download must never install.
"""

from __future__ import annotations

import io
import zipfile
from pathlib import Path
from urllib.request import Request, urlopen

from PySide6.QtCore import QThread, Signal

from zlog.core.adbfetch import verify_download
from zlog.core.adbpath import managed_adb_path
from zlog.core.applog import get_logger

_log = get_logger()

_CHUNK = 65536


def _safe_extract(zf: zipfile.ZipFile, dest_dir: Path) -> None:
    """Extract, refusing any entry that would land outside `dest_dir`. Belt
    and suspenders: the archive is already hash-verified against a pinned
    known-good build, but a zip's path entries are still untrusted input."""
    dest_root = dest_dir.resolve()
    for member in zf.namelist():
        target = (dest_root / member).resolve()
        if target != dest_root and dest_root not in target.parents:
            raise ValueError(f"Unsafe path in archive: {member!r}")
    zf.extractall(dest_root)


class AdbFetcher(QThread):
    progress = Signal(int, int)  # bytes read, total bytes (0 if unknown)
    done = Signal(str)  # path to the extracted adb executable
    error = Signal(str)

    def __init__(self, url: str, expected_sha256: str, dest_dir: str, parent=None):
        super().__init__(parent)
        self.url = url
        self.expected_sha256 = expected_sha256
        # Where platform-tools/ is unzipped to — the app-data root, not the
        # platform-tools folder itself (see core/adbpath.managed_adb_path).
        self.dest_dir = dest_dir
        self._cancelled = False

    def cancel(self) -> None:
        """Best-effort: stops at the next chunk boundary, not mid-read."""
        self._cancelled = True

    def run(self) -> None:
        try:
            data = self._download()
        except Exception as exc:
            if not self._cancelled:
                _log.exception("adb download failed")
                self.error.emit(f"Download failed: {exc}")
            return
        if self._cancelled:
            return
        if not verify_download(data, self.expected_sha256):
            _log.error("adb download failed verification (%d bytes)", len(data))
            self.error.emit("Downloaded file failed verification — nothing was installed.")
            return
        try:
            path = self._install(data)
        except Exception as exc:
            _log.exception("Could not install fetched adb")
            self.error.emit(f"Could not install adb: {exc}")
            return
        _log.info("adb fetched and installed: %s", path)
        self.done.emit(path)

    def _download(self) -> bytes:
        req = Request(self.url, headers={"User-Agent": "zlog-adb-fetch"})
        chunks: list[bytes] = []
        read = 0
        with urlopen(req, timeout=30) as resp:
            total = int(resp.headers.get("Content-Length") or 0)
            while not self._cancelled:
                chunk = resp.read(_CHUNK)
                if not chunk:
                    break
                chunks.append(chunk)
                read += len(chunk)
                self.progress.emit(read, total)
        return b"" if self._cancelled else b"".join(chunks)

    def _install(self, data: bytes) -> str:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            _safe_extract(zf, Path(self.dest_dir))
        return managed_adb_path(self.dest_dir)
