"""Tests for `core.extract` — regex named-group extraction and JSON
auto-detection. No Qt required."""

from __future__ import annotations

from zlog.core.extract import compile_extractors, extract, extract_json


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


# --- extract_json ------------------------------------------------------------


def test_extract_json_whole_message():
    assert extract_json('{"status": 200, "ok": true}') == {"status": "200", "ok": "true"}


def test_extract_json_embedded_in_text():
    msg = 'INFO: request done {"status": 200, "path": "/x"}'
    assert extract_json(msg) == {"status": "200", "path": "/x"}


def test_extract_json_flattens_one_level():
    msg = '{"user": {"id": 5, "name": "a"}, "count": 3}'
    assert extract_json(msg) == {"user.id": "5", "user.name": "a", "count": "3"}


def test_extract_json_null_and_bool():
    assert extract_json('{"a": null, "b": false}') == {"a": "null", "b": "false"}


def test_extract_json_malformed_returns_empty():
    assert extract_json("not json at all") == {}
    assert extract_json("{unterminated") == {}
    assert extract_json("") == {}


def test_extract_json_non_object_returns_empty():
    # A bare JSON array/number/string is valid JSON but not an "object of
    # fields" — nothing sensible to flatten, so treat it like no match.
    assert extract_json("[1, 2, 3]") == {}
    assert extract_json("42") == {}


def test_extract_json_never_raises_on_pathological_input():
    assert extract_json("{{{{{{{{" * 1000) == {}
