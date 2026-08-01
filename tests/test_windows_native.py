"""Genuinely-native Windows assertions — real ctypes calls against this
process, not the cross-platform logic (which the rest of the suite already
exercises everywhere by forcing `is_supported() -> True`). Skipped off win32
via the `windows_only` marker (see conftest.py and docs/plans/ci-windows-job.md).
"""

from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.windows_only


def test_list_processes_contains_this_process():
    from zlog.winlog.processes import list_processes

    procs = list_processes()
    assert procs, "Toolhelp snapshot returned no processes"
    assert any(p.pid == os.getpid() for p in procs)


def test_procnames_resolves_this_process():
    from zlog.winlog.procnames import ProcessNameCache

    name = ProcessNameCache().name_for(os.getpid())
    assert name, "expected a non-empty image name for the current process"
    assert name.lower().endswith(".exe")


def test_file_key_distinguishes_two_real_files(tmp_path):
    from zlog.ui.file_follower import file_key

    a = tmp_path / "a.log"
    b = tmp_path / "b.log"
    a.write_text("a")
    b.write_text("b")

    key_a, key_b = file_key(str(a)), file_key(str(b))
    assert key_a is not None and key_b is not None
    assert key_a != key_b
    assert len(key_a) == 3  # (ino, dev, st_ctime) — the Windows-only branch
