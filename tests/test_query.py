"""Tests for the query-bar parser — pure, no Qt."""

from zlog.core.query import parse_query


def test_plain_search():
    q = parse_query("connection timeout")
    assert q.search == "connection timeout" and not q.regex and q.level is None


def test_level_and_tag_and_package():
    q = parse_query("level:e tag:Activity package:com.example rest")
    assert q.level == "E" and q.tag == "Activity" and q.package == "com.example"
    assert q.search == "rest"


def test_exclude_repeatable():
    q = parse_query("boom -GnssHal -Sensors")
    assert q.search == "boom" and q.excludes == ("GnssHal", "Sensors")


def test_regex():
    q = parse_query('"/Skipped \\d+ frames/"')
    assert q.regex and q.search == "Skipped \\d+ frames"


def test_quoted_spaces():
    q = parse_query('tag:Foo "two words" -"a b"')
    assert q.tag == "Foo" and q.search == "two words" and q.excludes == ("a b",)


def test_bad_level_ignored():
    q = parse_query("level:ZZZ hello")
    assert q.level is None and q.search == "level:ZZZ hello"


def test_empty():
    q = parse_query("")
    assert q.search == "" and q.level is None and q.excludes == ()
