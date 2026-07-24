"""Pure DBWIN (OutputDebugString) parsing/mapping. No Qt, no OS APIs, no display."""

from __future__ import annotations

import struct
from datetime import datetime

from zlog.core.dbwin import build_entry, format_time, infer_level, parse_dbwin_record


def _rec(pid: int, message: bytes) -> bytes:
    # DBWIN layout: <DWORD pid><NUL-terminated ANSI string><stale padding>
    return struct.pack("<I", pid) + message + b"\x00" + b"\xcc" * 8


def test_parse_basic():
    assert parse_dbwin_record(_rec(1234, b"hello world")) == (1234, "hello world")


def test_parse_strips_trailing_newline():
    assert parse_dbwin_record(_rec(7, b"line\r\n")) == (7, "line")


def test_parse_empty_message():
    assert parse_dbwin_record(_rec(42, b"")) == (42, "")


def test_parse_stops_at_first_nul():
    # Only bytes up to the first NUL are the message; the rest is stale.
    assert parse_dbwin_record(struct.pack("<I", 9) + b"msg\x00garbage\x00") == (9, "msg")


def test_parse_missing_nul_takes_rest():
    assert parse_dbwin_record(struct.pack("<I", 5) + b"no terminator") == (5, "no terminator")


def test_parse_short_buffer():
    assert parse_dbwin_record(b"\x01\x02") == (0, "")


def test_parse_undecodable_bytes_replaced():
    pid, msg = parse_dbwin_record(struct.pack("<I", 1) + b"a\xff\xfeb\x00")
    assert pid == 1 and msg.startswith("a") and msg.endswith("b")  # no exception


def test_infer_level():
    assert infer_level("just some info") == "I"
    assert infer_level("NullReferenceException thrown") == "E"
    assert infer_level("connection failed") == "E"
    assert infer_level("WARN: retrying") == "W"
    assert infer_level("Fatal: out of memory") == "E"


def test_format_time():
    dt = datetime(2026, 7, 24, 9, 8, 7, 123456)
    assert format_time(dt) == "07-24 09:08:07.123"


def test_build_entry_maps_fields():
    dt = datetime(2026, 7, 24, 1, 2, 3, 4000)
    e = build_entry(1234, "myapp.exe", "boot error: disk", dt)
    assert e.pid == "1234"
    assert e.tid == ""
    assert e.tag == "myapp.exe"
    assert e.level == "E"
    assert e.message == "boot error: disk"
    assert e.source == "dbwin"
    assert e.time == "07-24 01:02:03.004"


def test_build_entry_falls_back_to_pid_tag():
    e = build_entry(99, "", "hi", datetime(2026, 7, 24, 0, 0, 0))
    assert e.tag == "99"


def test_build_entry_infer_off():
    e = build_entry(1, "a", "some error here", datetime(2026, 7, 24, 0, 0, 0), infer=False)
    assert e.level == "I"
