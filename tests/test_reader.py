"""AdbReader: the Popen decode settings, and that a read-loop failure reaches
`error` instead of silently killing the thread (regression for a reported
UnicodeDecodeError crash when logcat emits bytes outside cp1252)."""

from __future__ import annotations

import subprocess

from zlog.adb.reader import AdbReader


class _FakeProc:
    def __init__(self, lines):
        self.stdout = iter(lines)
        self.terminated = False

    def terminate(self):
        self.terminated = True


def test_run_decodes_stdout_as_utf8_with_replace(qapp, monkeypatch):
    """The Popen call must pin utf-8/replace rather than inherit the platform
    default text encoding (cp1252 on Windows), which raised on real logcat
    output."""
    seen_kwargs = {}

    def fake_popen(cmd, **kwargs):
        seen_kwargs.update(kwargs)
        return _FakeProc([])

    monkeypatch.setattr(subprocess, "Popen", fake_popen)
    reader = AdbReader()
    reader.run()

    assert seen_kwargs["encoding"] == "utf-8"
    assert seen_kwargs["errors"] == "replace"


def test_run_ends_cleanly_on_normal_eof_no_spurious_error(qapp, monkeypatch):
    """Stop() ends the stream via terminate() -> stdout EOF, a normal iterator
    exhaustion rather than an exception; that path must not trip the new error
    handling added for the crash fix."""
    lines = [
        "06-30 12:34:56.001 1 1 I Tag: one\n",
        "06-30 12:34:56.002 1 1 I Tag: two\n",
    ]

    def fake_popen(cmd, **kwargs):
        return _FakeProc(lines)

    monkeypatch.setattr(subprocess, "Popen", fake_popen)
    reader = AdbReader()
    batches = []
    errors = []
    reader.batch_ready.connect(batches.append)
    reader.error.connect(errors.append)

    reader.run()

    assert errors == []
    assert len(batches) == 1 and len(batches[0]) == 2


def test_run_reports_error_and_keeps_prior_batch_on_read_failure(qapp, monkeypatch):
    """A raw line that still blows up mid-stream must reach `error`, not raise
    out of run() and kill the thread silently."""

    class _ExplodingLines:
        def __init__(self):
            self._sent_first = False

        def __iter__(self):
            return self

        def __next__(self):
            if not self._sent_first:
                self._sent_first = True
                return "06-30 12:34:56.001 1 1 I Tag: ok\n"
            raise UnicodeDecodeError("utf-8", b"\x90", 0, 1, "bad byte")

    def fake_popen(cmd, **kwargs):
        proc = _FakeProc([])
        proc.stdout = _ExplodingLines()
        return proc

    monkeypatch.setattr(subprocess, "Popen", fake_popen)
    reader = AdbReader()
    batches = []
    errors = []
    reader.batch_ready.connect(batches.append)
    reader.error.connect(errors.append)

    reader.run()  # must return normally, not raise

    assert len(batches) == 1 and len(batches[0]) == 1  # prior line flushed
    assert len(errors) == 1 and "Log reading stopped" in errors[0]
