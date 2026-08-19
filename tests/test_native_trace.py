"""Tests for core/native_trace.py — native backtrace frame parsing/rewriting.
See docs/plans/crash-symbolication.md.
"""

from __future__ import annotations

from zlog.core.native_trace import NativeFrame, parse_native_frame, rewrite_native_frame


def test_parses_an_unresolved_frame_with_offset_placeholder():
    line = "    #00 pc 00012345  /data/app/~~xxx/base.apk!libnative.so (offset 0x3000)"
    frame = parse_native_frame(line)
    assert frame == NativeFrame(lib="libnative.so", offset="00012345")


def test_parses_a_bare_frame_with_no_suffix():
    line = "#00 pc 00012345  /system/lib64/libfoo.so"
    assert parse_native_frame(line) == NativeFrame(lib="libfoo.so", offset="00012345")


def test_already_symbolicated_frame_is_not_a_candidate():
    line = "#01 pc 00001a2b  /system/lib64/libc.so (abort+164)"
    assert parse_native_frame(line) is None


def test_non_frame_line_returns_none():
    assert parse_native_frame("FATAL EXCEPTION: main") is None
    assert parse_native_frame("    at com.example.App.method(App.java:1)") is None


def test_rewrite_inserts_the_symbol():
    line = "    #00 pc 00012345  /data/app/~~xxx/base.apk!libnative.so (offset 0x3000)"
    out = rewrite_native_frame(line, "my_function+32")
    assert out == "    #00 pc 00012345  /data/app/~~xxx/base.apk!libnative.so (my_function+32)"


def test_rewrite_on_a_bare_frame_with_no_prior_suffix():
    line = "#00 pc 00012345  /system/lib64/libfoo.so"
    out = rewrite_native_frame(line, "some_func")
    assert out == "#00 pc 00012345  /system/lib64/libfoo.so (some_func)"


def test_rewrite_on_a_non_frame_line_is_a_noop():
    line = "not a frame at all"
    assert rewrite_native_frame(line, "x") == line
