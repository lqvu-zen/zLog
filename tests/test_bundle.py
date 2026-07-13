"""Tests for the pure session-bundle serializer. No Qt required."""

import pytest

from zlog.core.bundle import make_bundle, parse_bundle


def test_bundle_roundtrips():
    text = make_bundle("06-30 12:00:00.000 1 2 I T: hi\n", "level:E boom", {"T": "#ff0000"}, [0, 2])
    got = parse_bundle(text)
    assert got["log"] == "06-30 12:00:00.000 1 2 I T: hi\n"
    assert got["query"] == "level:E boom"
    assert got["tag_highlights"] == {"T": "#ff0000"}
    assert got["bookmarks"] == [0, 2]


def test_parse_bundle_tolerates_junk():
    got = parse_bundle('{"query": 5, "bookmarks": ["x", 3, true], "tag_highlights": "nope"}')
    assert got["log"] == "" and got["query"] == ""
    assert got["tag_highlights"] == {}
    assert got["bookmarks"] == [3]  # only real ints (not the bool) survive


def test_parse_bundle_bad_json_raises():
    with pytest.raises(ValueError):
        parse_bundle("not json {")
