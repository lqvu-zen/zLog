"""Tests for timestamp formatting — pure, no Qt."""

from datetime import time, timedelta

from zlog.core.timefmt import first_at_or_after, format_delta, parse_logcat_time, parse_time_of_day


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


def test_parse_time_of_day_plain():
    assert parse_time_of_day("12:34:56") == time(12, 34, 56)
    assert parse_time_of_day("12:34:56.789") == time(12, 34, 56, 789_000)


def test_parse_time_of_day_tolerates_date_prefix():
    assert parse_time_of_day("06-30 12:34:56") == time(12, 34, 56)
    assert parse_time_of_day("06-30 12:34:56.789") == time(12, 34, 56, 789_000)


def test_parse_time_of_day_invalid_and_empty():
    assert parse_time_of_day("") is None
    assert parse_time_of_day("not a time") is None
    assert parse_time_of_day("25:00:00") is None


def test_first_at_or_after_finds_exact_or_later():
    times = ["06-30 10:00:00.000", "06-30 10:00:05.000", "06-30 10:00:10.000"]
    assert first_at_or_after(times, time(10, 0, 5)) == 1
    assert first_at_or_after(times, time(10, 0, 6)) == 2  # first row at/after


def test_first_at_or_after_none_when_all_before():
    times = ["06-30 10:00:00.000", "06-30 10:00:05.000"]
    assert first_at_or_after(times, time(11, 0, 0)) is None


def test_first_at_or_after_first_row_when_target_is_earliest():
    times = ["06-30 10:00:00.000", "06-30 10:00:05.000"]
    assert first_at_or_after(times, time(9, 0, 0)) == 0


def test_first_at_or_after_skips_unparseable_entries():
    times = ["", "06-30 10:00:05.000"]
    assert first_at_or_after(times, time(10, 0, 0)) == 1
