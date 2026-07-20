"""Tests for headless tail mode and the shared logfilter predicate (Qt-free)."""

from __future__ import annotations

import io

from zlog.cli import format_entry, run_tail
from zlog.core.logfilter import build_predicate
from zlog.core.models import LogEntry
from zlog.core.query import parse_query


def _e(level="I", tag="Tag", message="hello world", pid="100", tid="200", time="12:00:00.000"):
    return LogEntry(time, pid, tid, level, tag, message)


def test_predicate_min_level():
    ok = build_predicate(parse_query("level:W"))
    assert ok(_e(level="E"))
    assert ok(_e(level="W"))
    assert not ok(_e(level="I"))


def test_predicate_exact_level_set():
    ok = build_predicate(parse_query("level:I,E"))
    assert ok(_e(level="I"))
    assert ok(_e(level="E"))
    assert not ok(_e(level="W"))


def test_predicate_tag_and_search_and_exclude():
    ok = build_predicate(parse_query("tag:Foo boot -noise"))
    assert ok(_e(tag="Foobar", message="boot done"))
    assert not ok(_e(tag="Other", message="boot done"))  # tag gate
    assert not ok(_e(tag="Foobar", message="no match here"))  # search gate
    assert not ok(_e(tag="Foobar", message="boot noise"))  # exclude gate


def test_predicate_pid_include_and_exclude():
    inc = build_predicate(parse_query("pid:100,101"))
    assert inc(_e(pid="100")) and inc(_e(pid="101"))
    assert not inc(_e(pid="999"))
    exc = build_predicate(parse_query("-pid:100"))
    assert not exc(_e(pid="100"))
    assert exc(_e(pid="101"))


def test_predicate_regex_search():
    ok = build_predicate(parse_query("/wo.ld/"))
    assert ok(_e(message="hello world"))
    assert not ok(_e(message="hello there"))


def test_format_entry_shape():
    line = format_entry(_e(pid="3217", tid="9836", level="D", tag="T", message="m"))
    assert line == "12:00:00.000 3217-9836 D T: m"


def test_run_tail_filters_stream_to_out():
    raw_lines = [
        "07-15 20:09:03.024  100  200 I KeepTag: keep this\n",
        "07-15 20:09:03.025  100  200 I DropTag: drop this\n",
        "07-15 20:09:03.026  100  200 E KeepTag: keep error\n",
    ]

    class FakeProc:
        def __init__(self):
            self.stdout = iter(raw_lines)
            self.terminated = False

        def terminate(self):
            self.terminated = True

    proc = FakeProc()
    out = io.StringIO()
    code = run_tail(None, "tag:KeepTag", "adb", None, 0, out=out, _spawn=lambda: proc)
    assert code == 0
    body = out.getvalue()
    assert "keep this" in body and "keep error" in body
    assert "drop this" not in body
    assert proc.terminated  # the subprocess is cleaned up


def test_run_tail_missing_adb_returns_2():
    def boom():
        raise FileNotFoundError

    code = run_tail(None, "", "nope-adb", None, 0, out=io.StringIO(), _spawn=boom)
    assert code == 2
