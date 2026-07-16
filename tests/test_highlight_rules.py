"""Tests for persistent highlight rules — pure, no Qt."""

from zlog.core.highlight_rules import make_rule, normalize_rules


def test_make_rule_defaults_and_coercion():
    r = make_rule("boom", regex=1, color="#ff0000")
    assert r == {"pattern": "boom", "regex": True, "color": "#ff0000"}


def test_make_rule_default_color_when_falsy():
    assert make_rule("boom", color="")["color"] == "#ffeb3b"


def test_normalize_drops_junk():
    raw = [make_rule("Good"), "nope", {"no_pattern": 1}, {"pattern": "  "}, 42]
    out = normalize_rules(raw)
    assert [r["pattern"] for r in out] == ["Good"]


def test_normalize_non_list():
    assert normalize_rules(None) == []


def test_normalize_coerces_missing_fields():
    out = normalize_rules([{"pattern": "boom"}])
    assert out == [{"pattern": "boom", "regex": False, "color": "#ffeb3b"}]
