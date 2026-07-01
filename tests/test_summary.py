"""Tests for the status-bar level summary. No Qt, no display required."""

from zlog.core.summary import format_level_summary


def test_empty():
    assert format_level_summary(0, {}) == "0 lines"


def test_counts_severity_first_and_omit_zero():
    counts = {"I": 900, "W": 30, "E": 12, "F": 2, "D": 0, "V": 0}
    assert format_level_summary(944, counts) == "944 lines  F:2 E:12 W:30 I:900"


def test_thousands_separator():
    assert format_level_summary(1204, {"E": 1}).startswith("1,204 lines")


def test_only_total_when_no_known_levels():
    # unparsed lines have level "" and don't appear under any letter
    assert format_level_summary(5, {"": 5}) == "5 lines"
