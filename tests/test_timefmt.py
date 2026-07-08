"""Tests for timestamp formatting — pure, no Qt."""

from datetime import timedelta

from zlog.core.timefmt import format_delta, parse_logcat_time


def test_parse_valid():
    t = parse_logcat_time("06-30 12:34:56.789")
    assert t is not None and t.month == 6 and t.day == 30 and t.second == 56


def test_parse_invalid_and_empty():
    assert parse_logcat_time("") is None
    assert parse_logcat_time("not a time") is None
    assert parse_logcat_time("12:00:00.000") is None  # missing MM-DD


def test_parse_diff_is_a_duration():
    a = parse_logcat_time("06-30 12:00:00.000")
    b = parse_logcat_time("06-30 12:00:01.250")
    assert (b - a).total_seconds() == 1.25


def test_format_delta_compact():
    assert format_delta(timedelta(0)) == "+0.000"
    assert format_delta(timedelta(seconds=0.75)) == "+0.750"
    assert format_delta(timedelta(seconds=83.45)) == "+1:23.450"
    assert format_delta(timedelta(seconds=3661.5)) == "+1:01:01.500"
    assert format_delta(timedelta(seconds=-0.75)) == "-0.750"
