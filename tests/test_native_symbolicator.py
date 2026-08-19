"""Tests for ui/native_symbolicator.py's NativeSymbolResolver, against a
stubbed subprocess.run (no real addr2line/toolchain needed). Calls .run()
directly rather than .start() — pure logic + signal emission, no need for a
real background thread in tests. See docs/plans/crash-symbolication.md.
"""

from __future__ import annotations

import subprocess

from zlog.ui import native_symbolicator as mod
from zlog.ui.native_symbolicator import NativeSymbolResolver


def _capture(resolver):
    result = {}
    resolver.resolved.connect(lambda d: result.setdefault("value", d))
    resolver.run()
    return result.get("value")


def test_batches_offsets_per_library_into_one_subprocess_call(qapp, monkeypatch, tmp_path):
    so = tmp_path / "libfoo.so"
    so.write_bytes(b"")
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append((cmd, kwargs.get("input")))

        class R:
            stdout = "func_a\nfile.cpp:1\nfunc_b\nfile.cpp:2\n"
            stderr = ""

        return R()

    monkeypatch.setattr(mod.subprocess, "run", fake_run)
    resolver = NativeSymbolResolver(
        pairs=[("libfoo.so", "1000"), ("libfoo.so", "2000")],
        symbols_dir=str(tmp_path),
        addr2line_exe="addr2line",
        device_abi=None,
    )
    result = _capture(resolver)
    assert len(calls) == 1  # one subprocess call for both offsets in this library
    assert result == {("libfoo.so", "1000"): "func_a", ("libfoo.so", "2000"): "func_b"}


def test_missing_symbol_file_resolves_to_none_without_calling_addr2line(
    qapp, monkeypatch, tmp_path
):
    calls = []
    monkeypatch.setattr(mod.subprocess, "run", lambda *a, **k: calls.append(1))
    resolver = NativeSymbolResolver(
        pairs=[("libmissing.so", "1000")],
        symbols_dir=str(tmp_path),
        addr2line_exe="addr2line",
        device_abi=None,
    )
    result = _capture(resolver)
    assert result == {("libmissing.so", "1000"): None}
    assert calls == []  # never even tried to run addr2line


def test_subprocess_error_resolves_to_none_rather_than_raising(qapp, monkeypatch, tmp_path):
    so = tmp_path / "libfoo.so"
    so.write_bytes(b"")

    def fake_run(cmd, **kwargs):
        raise OSError("addr2line not found")

    monkeypatch.setattr(mod.subprocess, "run", fake_run)
    resolver = NativeSymbolResolver(
        pairs=[("libfoo.so", "1000")],
        symbols_dir=str(tmp_path),
        addr2line_exe="addr2line",
        device_abi=None,
    )
    result = _capture(resolver)
    assert result == {("libfoo.so", "1000"): None}


def test_timeout_resolves_to_none_rather_than_raising(qapp, monkeypatch, tmp_path):
    so = tmp_path / "libfoo.so"
    so.write_bytes(b"")

    def fake_run(cmd, **kwargs):
        raise subprocess.TimeoutExpired(cmd, kwargs.get("timeout", 15))

    monkeypatch.setattr(mod.subprocess, "run", fake_run)
    resolver = NativeSymbolResolver(
        pairs=[("libfoo.so", "1000")],
        symbols_dir=str(tmp_path),
        addr2line_exe="addr2line",
        device_abi=None,
    )
    result = _capture(resolver)
    assert result == {("libfoo.so", "1000"): None}


def test_cancel_before_run_emits_nothing(qapp, monkeypatch, tmp_path):
    def _boom(*a, **k):
        raise AssertionError("subprocess.run must not be called after cancel()")

    monkeypatch.setattr(mod.subprocess, "run", _boom)
    resolver = NativeSymbolResolver(
        pairs=[("libfoo.so", "1000")],
        symbols_dir=str(tmp_path),
        addr2line_exe="addr2line",
        device_abi=None,
    )
    resolver.cancel()
    result = _capture(resolver)
    assert result is None


def test_two_libraries_resolve_independently(qapp, monkeypatch, tmp_path):
    (tmp_path / "liba.so").write_bytes(b"")
    (tmp_path / "libb.so").write_bytes(b"")
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd[-1])  # the -e <so_path> arg is last

        class R:
            stdout = "some_func\nfile.cpp:1\n"
            stderr = ""

        return R()

    monkeypatch.setattr(mod.subprocess, "run", fake_run)
    resolver = NativeSymbolResolver(
        pairs=[("liba.so", "1000"), ("libb.so", "2000")],
        symbols_dir=str(tmp_path),
        addr2line_exe="addr2line",
        device_abi=None,
    )
    result = _capture(resolver)
    assert len(calls) == 2  # one subprocess call per distinct library
    assert result[("liba.so", "1000")] == "some_func"
    assert result[("libb.so", "2000")] == "some_func"
