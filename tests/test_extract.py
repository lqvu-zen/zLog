"""Tests for regex named-group field extraction (pure, no Qt)."""

from zlog.core.extract import compile_extractors, extract


def test_single_named_group():
    pats = compile_extractors([r"latency=(?P<ms>\d+)ms"])
    assert extract("req done latency=42ms ok", pats) == {"ms": "42"}


def test_multiple_groups_and_patterns():
    pats = compile_extractors([r"latency=(?P<ms>\d+)ms", r"url=(?P<url>\S+)"])
    got = extract("latency=7ms url=/api/v1 done", pats)
    assert got == {"ms": "7", "url": "/api/v1"}


def test_non_match_contributes_nothing():
    pats = compile_extractors([r"latency=(?P<ms>\d+)ms"])
    assert extract("nothing here", pats) == {}


def test_first_match_wins_across_patterns():
    pats = compile_extractors([r"a=(?P<v>\d+)", r"b=(?P<v>\d+)"])
    assert extract("a=1 b=2", pats) == {"v": "1"}  # first pattern's group wins


def test_invalid_pattern_is_skipped():
    pats = compile_extractors([r"(?P<x>\d+", r"y=(?P<y>\d+)"])  # first is malformed
    assert len(pats) == 1
    assert extract("y=9", pats) == {"y": "9"}


def test_pattern_without_named_group_is_dropped():
    assert compile_extractors([r"\d+"]) == []  # no named groups -> extracts nothing
