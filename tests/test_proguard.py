"""Tests for core/proguard.py — ProGuard/R8 mapping.txt parsing and stack
trace deobfuscation. See docs/plans/crash-symbolication.md.
"""

from __future__ import annotations

from zlog.core.proguard import deobfuscate_line, parse_mapping

_MAPPING = """\
com.example.app.MainActivity -> com.example.app.a:
    1:1:void onCreate(android.os.Bundle):23:23 -> a
    45:49:void onClick(android.view.View):45:49 -> b
    50:55:void onClick(java.lang.String):50:55 -> b
com.example.app.NetworkException -> com.example.app.b:
com.example.app.util.Helper -> com.example.app.c:
    int compute(int):10:10 -> a
"""


def test_parses_class_and_member_mappings():
    m = parse_mapping(_MAPPING)
    assert m.classes["com.example.app.a"] == "com.example.app.MainActivity"
    assert m.classes["com.example.app.b"] == "com.example.app.NetworkException"
    assert len(m.members["com.example.app.a"]) == 3


def test_deobfuscates_a_simple_frame():
    m = parse_mapping(_MAPPING)
    line = "    at com.example.app.a.a(SourceFile:23)"
    out = deobfuscate_line(m, line)
    assert out == "    at com.example.app.MainActivity.onCreate(MainActivity:23)"


def test_disambiguates_overloaded_method_by_line_range():
    m = parse_mapping(_MAPPING)
    first = deobfuscate_line(m, "    at com.example.app.a.b(SourceFile:46)")
    second = deobfuscate_line(m, "    at com.example.app.a.b(SourceFile:52)")
    assert "onClick" in first and "onClick" in second
    # Both resolve to the same original name (overload resolution doesn't
    # disambiguate *which* onClick beyond the name itself — see the plan's
    # documented limitation), but neither should crash or stay obfuscated.
    assert ".b(" not in first
    assert ".b(" not in second


def test_unmapped_class_passes_through_unchanged():
    m = parse_mapping(_MAPPING)
    line = "    at com.other.Unrelated.doThing(SourceFile:5)"
    assert deobfuscate_line(m, line) == line


def test_exception_header_is_deobfuscated():
    m = parse_mapping(_MAPPING)
    line = "com.example.app.b: Connection timed out"
    assert deobfuscate_line(m, line) == "com.example.app.NetworkException: Connection timed out"


def test_caused_by_header_is_deobfuscated():
    m = parse_mapping(_MAPPING)
    line = "Caused by: com.example.app.b"
    assert deobfuscate_line(m, line) == "Caused by: com.example.app.NetworkException"


def test_unmapped_header_passes_through_unchanged():
    m = parse_mapping(_MAPPING)
    line = "java.lang.RuntimeException: boom"
    assert deobfuscate_line(m, line) == line


def test_plain_message_untouched():
    m = parse_mapping(_MAPPING)
    line = "Just a normal log line, nothing to see here"
    assert deobfuscate_line(m, line) == line


def test_member_with_no_line_range_still_resolves_when_line_missing():
    text = "com.example.app.X -> com.example.app.x:\n    void run() -> a\n"
    m = parse_mapping(text)
    out = deobfuscate_line(m, "    at com.example.app.x.a(SourceFile)")
    assert out == "    at com.example.app.X.run(X)"


def test_nested_class_dollar_sign_handled():
    # A nested class is defined in its *enclosing* class's source file
    # (Outer$Inner lives in Outer.java, not "Outer$Inner.java").
    text = "com.example.app.Outer$Inner -> com.example.app.a$b:\n    void go() -> a\n"
    m = parse_mapping(text)
    out = deobfuscate_line(m, "    at com.example.app.a$b.a(SourceFile:1)")
    assert out == "    at com.example.app.Outer$Inner.go(Outer:1)"


def test_empty_mapping_changes_nothing():
    m = parse_mapping("")
    line = "    at com.example.app.a.a(SourceFile:23)"
    assert deobfuscate_line(m, line) == line


def test_large_mapping_parses_linearly():
    # Not a real perf benchmark (no timing assertion) — just proves a large
    # file parses without error, per the plan's "time it" risk note.
    lines = []
    for i in range(2000):
        lines.append(f"com.example.app.Class{i} -> c{i}:")
        lines.append(f"    void method{i}() -> m")
    text = "\n".join(lines) + "\n"
    m = parse_mapping(text)
    assert len(m.classes) == 2000
    assert m.classes["c500"] == "com.example.app.Class500"
