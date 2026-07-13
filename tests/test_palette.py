"""Tests for the pure command-palette matcher. No Qt required."""

from zlog.core.palette import match_commands


def test_empty_query_returns_all_in_order():
    labels = ["Open Log", "Save Log", "Tag Summary"]
    assert match_commands(labels, "") == [0, 1, 2]


def test_substring_ranks_before_subsequence():
    labels = ["Clear Filters", "Clear device log buffer", "Collapse Repeated Lines"]
    # "clear" is a substring of the first two; index 0 and 1 come first
    res = match_commands(labels, "clear")
    assert res[:2] == [0, 1]
    assert 2 not in res  # "Collapse Repeated Lines" has no "clear" substring/subsequence


def test_subsequence_match():
    labels = ["Clear device log buffer", "Tag Summary"]
    # "cdb" is a subsequence of "clear device buffer"
    assert 0 in match_commands(labels, "cdb")


def test_no_match_excluded():
    assert match_commands(["Open", "Save"], "zzz") == []
