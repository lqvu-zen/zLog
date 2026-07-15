"""Tests for the search matcher. No Qt, no display required."""

import re

import pytest

from zlog.core.search import compile_matcher, find_spans


def test_empty_matches_everything():
    m = compile_matcher("", regex=False)
    assert m("anything") and m("")


def test_substring_is_case_insensitive():
    m = compile_matcher("Exception", regex=False)
    assert m("java.lang.NullPointerException")
    assert m("caused an exception here")
    assert not m("all good")


def test_regex_matches():
    m = compile_matcher(r"^Skipped \d+ frames", regex=True)
    assert m("Skipped 42 frames! Too much work")
    assert not m("did not skip")


def test_regex_is_case_insensitive():
    m = compile_matcher("exception|anr", regex=True)
    assert m("FATAL EXCEPTION: main")
    assert m("Reason: ANR in com.example")


def test_invalid_regex_raises():
    with pytest.raises(re.error):
        compile_matcher("(unclosed", regex=True)


def test_case_sensitive_substring():
    m = compile_matcher("Exception", regex=False, case=True)
    assert m("java.lang.NullPointerException")
    assert not m("caused an exception here")


def test_case_sensitive_regex():
    m = compile_matcher("ANR", regex=True, case=True)
    assert m("Reason: ANR in com.example")
    assert not m("minor anr-like text")


def test_find_spans_empty_term_returns_nothing():
    assert find_spans("anything", "", regex=False) == []


def test_find_spans_substring_case_insensitive():
    assert find_spans("java.lang.Exception here", "exception", regex=False) == [(10, 19)]


def test_find_spans_substring_multiple_non_overlapping():
    assert find_spans("abcabc", "abc", regex=False) == [(0, 3), (3, 6)]


def test_find_spans_case_sensitive():
    assert find_spans("Exception exception", "Exception", regex=False, case=True) == [(0, 9)]


def test_find_spans_regex():
    assert find_spans("Skipped 42 frames", r"\d+", regex=True) == [(8, 10)]


def test_find_spans_regex_multiple_matches():
    assert find_spans("a1 b22 c333", r"\d+", regex=True) == [(1, 2), (4, 6), (8, 11)]


def test_find_spans_regex_zero_width_does_not_hang():
    # A zero-width pattern must not loop forever; finditer already guards this.
    assert find_spans("abc", r"x*", regex=True) == [(0, 0), (1, 1), (2, 2), (3, 3)]


def test_find_spans_invalid_regex_raises():
    with pytest.raises(re.error):
        find_spans("abc", "(unclosed", regex=True)
