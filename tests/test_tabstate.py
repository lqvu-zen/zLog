"""Tab-state serialization. Pure: no Qt, no filesystem."""

from __future__ import annotations

from zlog.core.tabstate import MAX_TABS, TabState, tabs_from_json, tabs_to_json


def test_round_trip():
    states = [
        TabState(path="/logs/a.log", query="level:E", level="E", package="com.x"),
        TabState(path="/logs/b.log"),
    ]
    assert tabs_from_json(tabs_to_json(states)) == states


def test_empty_tab_is_not_persisted():
    """A blank tab with no file and no filter isn't worth restoring."""
    assert tabs_to_json([TabState()]) == []


def test_a_query_alone_is_worth_restoring():
    """A streaming tab has no file, but its filter is still worth keeping."""
    states = [TabState(query="level:E tag:Net")]
    assert tabs_from_json(tabs_to_json(states)) == states


def test_cap_on_save():
    many = [TabState(path=f"/logs/{i}.log") for i in range(MAX_TABS + 5)]
    assert len(tabs_to_json(many)) == MAX_TABS


def test_cap_on_load():
    data = [{"path": f"/logs/{i}.log"} for i in range(MAX_TABS + 5)]
    assert len(tabs_from_json(data)) == MAX_TABS


# --- defensive loading (the settings file is user-editable) ----------------
def test_non_list_is_ignored():
    assert tabs_from_json(None) == []
    assert tabs_from_json({"path": "x"}) == []
    assert tabs_from_json("nonsense") == []


def test_non_dict_entries_are_skipped():
    assert tabs_from_json(["x", 5, None, {"path": "/a.log"}]) == [TabState(path="/a.log")]


def test_missing_fields_get_defaults():
    assert tabs_from_json([{"path": "/a.log"}]) == [TabState(path="/a.log", level="V")]


def test_null_fields_are_coerced():
    got = tabs_from_json([{"path": "/a.log", "query": None, "level": None, "package": None}])
    assert got == [TabState(path="/a.log", query="", level="V", package="")]


def test_non_string_fields_are_stringified():
    got = tabs_from_json([{"path": 123, "query": 45}])
    assert got[0].path == "123" and got[0].query == "45"


def test_entry_with_nothing_useful_is_dropped():
    assert tabs_from_json([{"path": "", "query": "", "package": ""}]) == []
