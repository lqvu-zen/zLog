"""Tests for the adb download/verify/install QThread. No real network: `urlopen`
is monkeypatched to a fake response built in-process."""

from __future__ import annotations

import hashlib
import io
import sys
import zipfile

from PySide6.QtCore import QEventLoop, QTimer

from zlog.core.adbpath import managed_adb_path

_EXE = "adb.exe" if sys.platform == "win32" else "adb"


def _make_zip(member_name: str, content: bytes) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(member_name, content)
    return buf.getvalue()


class _FakeResponse:
    """A minimal stand-in for `http.client.HTTPResponse`: chunked `.read()`,
    a `.headers.get()`, and use as a context manager."""

    def __init__(self, data: bytes, chunk_size: int = 8):
        self._chunks = [data[i : i + chunk_size] for i in range(0, len(data), chunk_size)]
        self.headers = {"Content-Length": str(len(data))}

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self, _n=-1) -> bytes:
        return self._chunks.pop(0) if self._chunks else b""


def _run_and_wait(fetcher, qapp):
    result = {}
    fetcher.done.connect(lambda p: result.setdefault("done", p))
    fetcher.error.connect(lambda m: result.setdefault("error", m))
    loop = QEventLoop()
    fetcher.done.connect(loop.quit)
    fetcher.error.connect(loop.quit)
    QTimer.singleShot(5000, loop.quit)  # safety net
    fetcher.start()
    loop.exec()
    fetcher.wait(2000)
    return result


def test_fetch_verifies_and_installs(qapp, tmp_path, monkeypatch):
    import zlog.ui.adb_fetcher as mod

    data = _make_zip(f"platform-tools/{_EXE}", b"fake-adb-binary-content")
    digest = hashlib.sha256(data).hexdigest()
    monkeypatch.setattr(mod, "urlopen", lambda *a, **k: _FakeResponse(data))

    fetcher = mod.AdbFetcher("http://fake/pt.zip", digest, str(tmp_path))
    result = _run_and_wait(fetcher, qapp)

    expected_path = managed_adb_path(str(tmp_path))
    assert result.get("done") == expected_path
    assert "error" not in result
    from pathlib import Path

    assert Path(expected_path).read_bytes() == b"fake-adb-binary-content"


def test_tampered_download_fails_verification_and_installs_nothing(qapp, tmp_path, monkeypatch):
    import zlog.ui.adb_fetcher as mod

    data = _make_zip(f"platform-tools/{_EXE}", b"fake-adb-binary-content")
    wrong_digest = hashlib.sha256(data + b"x").hexdigest()  # doesn't match `data`
    monkeypatch.setattr(mod, "urlopen", lambda *a, **k: _FakeResponse(data))

    fetcher = mod.AdbFetcher("http://fake/pt.zip", wrong_digest, str(tmp_path))
    result = _run_and_wait(fetcher, qapp)

    assert "done" not in result
    assert "failed verification" in result.get("error", "")
    assert not (tmp_path / "platform-tools").exists()


def test_path_traversal_in_archive_is_rejected(qapp, tmp_path, monkeypatch):
    """Even a hash-verified archive shouldn't be trusted to extract safely —
    a member escaping the dest dir must not be written anywhere."""
    import zlog.ui.adb_fetcher as mod

    data = _make_zip("../../evil.txt", b"malicious")
    digest = hashlib.sha256(data).hexdigest()
    monkeypatch.setattr(mod, "urlopen", lambda *a, **k: _FakeResponse(data))

    fetcher = mod.AdbFetcher("http://fake/pt.zip", digest, str(tmp_path))
    result = _run_and_wait(fetcher, qapp)

    assert "done" not in result
    assert "Could not install" in result.get("error", "")
    assert not (tmp_path.parent / "evil.txt").exists()


def test_cancel_before_download_completes_emits_nothing(qapp, tmp_path, monkeypatch):
    import zlog.ui.adb_fetcher as mod

    data = _make_zip(f"platform-tools/{_EXE}", b"fake-adb-binary-content")
    digest = hashlib.sha256(data).hexdigest()

    class _SlowFakeResponse(_FakeResponse):
        def read(self, _n=-1):
            fetcher.cancel()  # cancel mid-download, after the very first chunk
            return super().read(_n)

    monkeypatch.setattr(mod, "urlopen", lambda *a, **k: _SlowFakeResponse(data))
    fetcher = mod.AdbFetcher("http://fake/pt.zip", digest, str(tmp_path))
    result = {}
    fetcher.done.connect(lambda p: result.setdefault("done", p))
    fetcher.error.connect(lambda m: result.setdefault("error", m))
    fetcher.start()
    fetcher.wait(2000)  # run() returns promptly once cancelled; no event loop needed
    qapp.processEvents()  # flush any queued signal delivery

    assert result == {}  # neither done nor error — cancellation is silent
    assert not (tmp_path / "platform-tools").exists()
