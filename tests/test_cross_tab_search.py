"""Tests for `ui.cross_tab_search` — pure aside from the stub session shape it
accepts (a `.model` with `all_entries()`), so no Qt/display is needed."""

from __future__ import annotations

from zlog.core.models import LogEntry
from zlog.core.query import parse_query
from zlog.ui.cross_tab_search import TabMatch, search_sessions, unsupported_gates


class _StubModel:
    def __init__(self, entries):
        self._entries = entries

    def all_entries(self):
        return list(self._entries)


class _StubSession:
    def __init__(self, entries):
        self.model = _StubModel(entries)


def _session(*messages):
    return _StubSession([LogEntry("t", "1", "1", "I", "T", m) for m in messages])


def test_finds_matches_across_several_tabs_in_order():
    sessions = [
        _session("alpha", "boom target"),
        _session("nothing here"),
        _session("another boom target", "quiet"),
    ]
    matches = search_sessions(sessions, parse_query("boom"))
    assert matches == [
        TabMatch(0, 1, sessions[0].model.all_entries()[1]),
        TabMatch(2, 0, sessions[2].model.all_entries()[0]),
    ]


def test_no_matches_returns_empty_list():
    sessions = [_session("alpha"), _session("beta")]
    assert search_sessions(sessions, parse_query("nope")) == []


def test_empty_sessions_list():
    assert search_sessions([], parse_query("anything")) == []


def test_level_and_tag_gates_apply_per_tab():
    sessions = [_StubSession([LogEntry("t", "1", "1", "E", "Crash", "oops")])]
    assert len(search_sessions(sessions, parse_query("level:E"))) == 1  # min-level floor
    assert search_sessions(sessions, parse_query("level:F")) == []  # Fatal outranks Error
    assert len(search_sessions(sessions, parse_query("tag:Crash"))) == 1


def test_unsupported_gates_flagged_without_crashing():
    # proc:/since:/until: are silently ignored by core.logfilter.build_predicate
    # (no live PID->name map or clock headlessly) — search must not crash, and
    # the caller is expected to warn using unsupported_gates() rather than the
    # search silently behaving differently from a same-tab query.
    sessions = [_session("hello")]
    spec = parse_query("proc:com.example since:10:00:00 hello")
    assert unsupported_gates(spec) is True
    assert len(search_sessions(sessions, spec)) == 1  # "hello" still matches

    assert unsupported_gates(parse_query("level:E tag:Activity")) is False
