"""Tests for parsing `ps` output into a PID -> name map — pure, no Qt."""

from zlog.core.processes import parse_ps


def test_parse_ps_two_column_form():
    out = "  PID NAME\n    1 init\n 4921 com.android.systemui\n"
    assert parse_ps(out) == {"1": "init", "4921": "com.android.systemui"}


def test_parse_ps_default_layout():
    out = (
        "USER   PID  PPID  VSZ  RSS WCHAN  PC  NAME\n"
        "u0_a1 4921     1  100   50 0      0 S com.android.systemui\n"
    )
    assert parse_ps(out)["4921"] == "com.android.systemui"


def test_parse_ps_skips_header_and_junk():
    out = "PID NAME\ngarbage\n\n123 com.example.app\n"
    got = parse_ps(out)
    assert got == {"123": "com.example.app"}


def test_parse_ps_empty():
    assert parse_ps("") == {}
