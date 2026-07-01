"""Tests for settings serialization. No Qt, no display required."""

import json

from zlog.core.settings import DEFAULTS, load_settings, save_settings


def test_missing_file_returns_defaults(tmp_path):
    assert load_settings(str(tmp_path / "nope.json")) == DEFAULTS


def test_round_trip(tmp_path):
    p = tmp_path / "settings.json"
    data = dict(DEFAULTS)
    data["theme"] = "Dark"
    data["follow"] = False
    data["min_level"] = "W"
    data["tag_highlights"] = {"Choreographer": "#b3e5fc"}
    save_settings(str(p), data)
    loaded = load_settings(str(p))
    assert loaded["theme"] == "Dark"
    assert loaded["follow"] is False
    assert loaded["min_level"] == "W"
    assert loaded["tag_highlights"] == {"Choreographer": "#b3e5fc"}


def test_corrupt_file_returns_defaults(tmp_path):
    p = tmp_path / "settings.json"
    p.write_text("{not valid json")
    assert load_settings(str(p)) == DEFAULTS


def test_unknown_keys_are_ignored(tmp_path):
    p = tmp_path / "settings.json"
    p.write_text(json.dumps({"theme": "Dark", "bogus": 1}))
    loaded = load_settings(str(p))
    assert loaded["theme"] == "Dark"
    assert "bogus" not in loaded


def test_defaults_not_mutated_by_caller(tmp_path):
    loaded = load_settings(str(tmp_path / "nope.json"))
    loaded["tag_highlights"]["X"] = "#fff"
    assert DEFAULTS["tag_highlights"] == {}
