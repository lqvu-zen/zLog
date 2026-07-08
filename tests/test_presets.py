"""Tests for filter presets — pure, no Qt."""

from zlog.core.presets import make_preset, normalize_presets, remove_preset, upsert_preset


def test_make_preset_defaults_and_coercion():
    p = make_preset("A", min_level="E", regex=1, case=0, search="x", package="com.x")
    assert p == {
        "name": "A",
        "min_level": "E",
        "search": "x",
        "regex": True,
        "case": False,
        "package": "com.x",
    }


def test_normalize_drops_junk():
    raw = [make_preset("Good"), "nope", {"no_name": 1}, {"name": "  "}, 42]
    out = normalize_presets(raw)
    assert [p["name"] for p in out] == ["Good"]


def test_normalize_non_list():
    assert normalize_presets(None) == []


def test_upsert_adds_sorted_and_replaces_by_name():
    ps = upsert_preset([], make_preset("beta"))
    ps = upsert_preset(ps, make_preset("Alpha"))
    assert [p["name"] for p in ps] == ["Alpha", "beta"]  # sorted case-insensitively
    ps = upsert_preset(ps, make_preset("alpha", search="new"))  # replaces "Alpha"
    names = [p["name"] for p in ps]
    assert names.count("Alpha") == 0 and "alpha" in names
    assert next(p for p in ps if p["name"] == "alpha")["search"] == "new"


def test_remove_preset():
    ps = [make_preset("A"), make_preset("B")]
    assert [p["name"] for p in remove_preset(ps, "a")] == ["B"]  # case-insensitive
