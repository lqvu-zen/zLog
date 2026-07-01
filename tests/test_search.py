"""Tests for the search matcher. No Qt, no display required."""

import re

import pytest

from zlog.core.search import compile_matcher


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
