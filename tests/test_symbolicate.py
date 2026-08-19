"""Tests for core/symbolicate.py's Symbolicator — composes native-then-Java,
respects the enabled toggle, no-ops with nothing loaded.
See docs/plans/crash-symbolication.md.
"""

from __future__ import annotations

from zlog.core.proguard import parse_mapping
from zlog.core.symbolicate import Symbolicator

_MAPPING = "com.example.app.MainActivity -> com.example.app.a:\n    void run() -> a\n"


def test_nothing_loaded_is_a_noop():
    s = Symbolicator()
    line = "at com.example.app.a.a(SourceFile:1)"
    assert s.apply(line) == line


def test_java_mapping_applied_when_loaded():
    s = Symbolicator()
    s.mapping = parse_mapping(_MAPPING)
    out = s.apply("at com.example.app.a.a(SourceFile:1)")
    assert "MainActivity" in out and "run" in out


def test_native_cache_applied_when_resolved():
    s = Symbolicator()
    s.native_cache[("libfoo.so", "00001000")] = "my_function"
    line = "#00 pc 00001000  /system/lib/libfoo.so (offset 0x1000)"
    out = s.apply(line)
    assert "my_function" in out


def test_native_frame_unresolved_leaves_line_unchanged():
    s = Symbolicator()
    line = "#00 pc 00001000  /system/lib/libfoo.so (offset 0x1000)"
    assert s.apply(line) == line


def test_native_frame_never_falls_through_to_java_mapping():
    # A native frame line doesn't look like a Java `at Class.method(...)`
    # frame, so it must not accidentally get mangled by deobfuscate_line.
    s = Symbolicator()
    s.mapping = parse_mapping(_MAPPING)
    line = "#00 pc 00001000  /system/lib/libfoo.so (offset 0x1000)"
    assert s.apply(line) == line


def test_disabled_toggle_returns_raw_text_without_discarding_state():
    s = Symbolicator()
    s.mapping = parse_mapping(_MAPPING)
    s.native_cache[("libfoo.so", "00001000")] = "my_function"
    s.enabled = False
    java_line = "at com.example.app.a.a(SourceFile:1)"
    native_line = "#00 pc 00001000  /system/lib/libfoo.so (offset 0x1000)"
    assert s.apply(java_line) == java_line
    assert s.apply(native_line) == native_line
    s.enabled = True
    assert "MainActivity" in s.apply(java_line)
    assert "my_function" in s.apply(native_line)


def test_plain_message_untouched():
    s = Symbolicator()
    s.mapping = parse_mapping(_MAPPING)
    s.native_cache[("libfoo.so", "00001000")] = "my_function"
    line = "Just a normal log message"
    assert s.apply(line) == line
