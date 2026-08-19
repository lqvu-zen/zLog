"""Tests for core/addr2line.py — command building and output parsing, no
subprocess involved. See docs/plans/crash-symbolication.md.
"""

from __future__ import annotations

from zlog.core.addr2line import build_command, build_stdin, parse_output


def test_build_command_shape():
    cmd = build_command("addr2line", "/path/to/libfoo.so")
    assert cmd == ["addr2line", "-f", "-C", "-e", "/path/to/libfoo.so"]


def test_build_stdin_one_offset_per_line():
    assert build_stdin(["1000", "2000"]) == "1000\n2000\n"


def test_parse_output_pairs_function_names_positionally():
    raw = "my_function\nfoo.cpp:12\nother_function\nbar.cpp:34\n"
    out = parse_output(raw, ["1000", "2000"])
    assert out == {"1000": "my_function", "2000": "other_function"}


def test_parse_output_skips_unresolved_question_marks():
    raw = "??\n??:0\nreal_function\nbaz.cpp:1\n"
    out = parse_output(raw, ["1000", "2000"])
    assert "1000" not in out
    assert out["2000"] == "real_function"


def test_parse_output_short_output_leaves_trailing_offsets_unresolved():
    raw = "only_one\nfile.cpp:1\n"
    out = parse_output(raw, ["1000", "2000", "3000"])
    assert out == {"1000": "only_one"}
    assert "2000" not in out and "3000" not in out


def test_parse_output_empty_raw():
    assert parse_output("", ["1000"]) == {}
