"""Headless tests for the Qt table model and filter proxy.

These run under the `offscreen` Qt platform (see conftest.py), so no display is
needed. They cover the filter *gates* — the logic that has historically hidden
bugs — without going through the full MainWindow.
"""

from __future__ import annotations

from zlog.core.models import LogEntry
from zlog.ui.log_model import LogFilterProxy, LogTableModel


def _entry(level="I", tag="Tag", message="msg", pid="100"):
    return LogEntry("12:00:00.000", pid, "200", level, tag, message)


def _wire(qapp):
    model = LogTableModel()
    proxy = LogFilterProxy()
    proxy.setSourceModel(model)
    return model, proxy


def _messages(model, proxy):
    return [
        model.entry_at(proxy.mapToSource(proxy.index(r, 0)).row()).message
        for r in range(proxy.rowCount())
    ]


def test_batch_update_collapses_invalidates_to_one(qapp):
    _, proxy = _wire(qapp)
    calls = []
    real_invalidate = proxy.invalidate
    proxy.invalidate = lambda: (calls.append(1), real_invalidate())[-1]
    with proxy.batch_update():
        proxy.set_min_level("W")
        proxy.set_tag("Foo")
        proxy.set_query_pids({"100"})
        proxy.set_proc("com.x")
        proxy.set_exclude_pids({"200"})
        proxy.set_exclude_proc("com.y")
        proxy.set_levels(["W", "E"])
        proxy.set_collapse(True)
        proxy.set_search("boom", regex=False)
    assert calls == [1]  # 9 setters, exactly 1 real invalidate


def test_batch_update_invalidates_once_even_on_exception(qapp):
    _, proxy = _wire(qapp)
    calls = []
    real_invalidate = proxy.invalidate
    proxy.invalidate = lambda: (calls.append(1), real_invalidate())[-1]
    try:
        with proxy.batch_update():
            proxy.set_tag("Foo")
            raise RuntimeError("boom")
    except RuntimeError:
        pass
    assert calls == [1]  # still invalidated once via the finally block


def test_setters_invalidate_normally_outside_batch_update(qapp):
    _, proxy = _wire(qapp)
    calls = []
    real_invalidate = proxy.invalidate
    proxy.invalidate = lambda: (calls.append(1), real_invalidate())[-1]
    proxy.set_tag("Foo")
    proxy.set_min_level("W")
    assert calls == [1, 1]  # each standalone setter still invalidates on its own


def test_append_and_count(qapp):
    model, proxy = _wire(qapp)
    model.append_entries([_entry(), _entry()])
    assert model.rowCount() == 2
    assert proxy.rowCount() == 2  # no filters => everything visible


def test_clear_empties_master_list(qapp):
    model, proxy = _wire(qapp)
    model.append_entries([_entry(), _entry()])
    model.clear()
    assert model.rowCount() == 0 and proxy.rowCount() == 0


def test_level_counts(qapp):
    model, _ = _wire(qapp)
    model.append_entries([_entry(level="E"), _entry(level="E"), _entry(level="W")])
    counts = model.level_counts()
    assert counts.get("E") == 2 and counts.get("W") == 1


def test_level_gate(qapp):
    model, proxy = _wire(qapp)
    model.append_entries(
        [
            _entry(level="V", message="v"),
            _entry(level="E", message="e"),
            _entry(level="I", message="i"),
        ]
    )
    proxy.set_min_level("E")
    assert _messages(model, proxy) == ["e"]


def test_unparsed_lines_pass_level_gate(qapp):
    # Banner/unparsed lines carry an empty level and must never be filtered out.
    model, proxy = _wire(qapp)
    model.append_entries([_entry(level="", message="--- beginning of main")])
    proxy.set_min_level("E")
    assert _messages(model, proxy) == ["--- beginning of main"]


def test_text_gate_case_insensitive_by_default(qapp):
    model, proxy = _wire(qapp)
    model.append_entries([_entry(message="Boom Exception"), _entry(message="all good")])
    assert proxy.set_search("exception", regex=False) is True
    assert _messages(model, proxy) == ["Boom Exception"]


def test_text_gate_case_sensitive(qapp):
    model, proxy = _wire(qapp)
    model.append_entries([_entry(message="Exception"), _entry(message="exception")])
    proxy.set_search("Exception", regex=False, case=True)
    assert _messages(model, proxy) == ["Exception"]


def test_regex_gate_and_invalid_pattern(qapp):
    model, proxy = _wire(qapp)
    model.append_entries([_entry(message="Skipped 42 frames"), _entry(message="ok")])
    assert proxy.set_search(r"Skipped \d+ frames", regex=True) is True
    assert _messages(model, proxy) == ["Skipped 42 frames"]
    # Invalid regex keeps the previous matcher and returns False.
    assert proxy.set_search("(unclosed", regex=True) is False
    assert _messages(model, proxy) == ["Skipped 42 frames"]


def test_search_matches_tag_and_message(qapp):
    model, proxy = _wire(qapp)
    model.append_entries(
        [_entry(tag="ActivityManager", message="x"), _entry(tag="Other", message="y")]
    )
    proxy.set_search("ActivityManager", regex=False)
    assert _messages(model, proxy) == ["x"]


def test_pid_gate(qapp):
    model, proxy = _wire(qapp)
    model.append_entries([_entry(pid="111", message="mine"), _entry(pid="222", message="theirs")])
    proxy.set_pids({"111"})
    assert _messages(model, proxy) == ["mine"]
    proxy.set_pids(None)  # cleared => all visible again
    assert len(_messages(model, proxy)) == 2


def test_combined_gates(qapp):
    model, proxy = _wire(qapp)
    model.append_entries(
        [
            _entry(pid="111", level="E", message="boom"),
            _entry(pid="111", level="I", message="info"),
            _entry(pid="222", level="E", message="other boom"),
        ]
    )
    proxy.set_pids({"111"})
    proxy.set_min_level("E")
    proxy.set_search("boom", regex=False)
    assert _messages(model, proxy) == ["boom"]


def test_highlight_does_not_filter(qapp):
    model, proxy = _wire(qapp)
    model.append_entries([_entry(message="boom"), _entry(message="quiet")])
    model.set_highlight("boom")
    assert proxy.rowCount() == 2  # highlight never hides rows


def test_highlight_tints_matching_row(qapp):
    from PySide6.QtCore import Qt

    model, _ = _wire(qapp)
    model.set_highlight_color("#123456")
    model.append_entries([_entry(message="boom"), _entry(message="quiet")])
    model.set_highlight("boom")
    bg0 = model.data(model.index(0, 0), Qt.BackgroundRole)
    bg1 = model.data(model.index(1, 0), Qt.BackgroundRole)
    assert bg0 is not None and bg0.name() == "#123456"
    assert bg1 is None  # non-match, level "I" has no tint


def test_highlight_cleared_by_empty(qapp):
    from PySide6.QtCore import Qt

    model, _ = _wire(qapp)
    model.append_entries([_entry(message="boom")])
    model.set_highlight("boom")
    model.set_highlight("")
    assert model.data(model.index(0, 0), Qt.BackgroundRole) is None


def test_match_spans_role_returns_spans_for_matching_row(qapp):
    from zlog.ui.log_model import MATCH_SPANS_ROLE

    model, _ = _wire(qapp)
    model.append_entries([_entry(message="a boom here"), _entry(message="quiet")])
    model.set_highlight("boom")
    spans0 = model.data(model.index(0, 0), MATCH_SPANS_ROLE)
    spans1 = model.data(model.index(1, 0), MATCH_SPANS_ROLE)
    assert spans0 == [(2, 6)]
    assert spans1 == []


def test_match_spans_role_empty_when_highlight_off(qapp):
    from zlog.ui.log_model import MATCH_SPANS_ROLE

    model, _ = _wire(qapp)
    model.append_entries([_entry(message="a boom here")])
    spans = model.data(model.index(0, 0), MATCH_SPANS_ROLE)
    assert spans == []


def test_match_spans_role_cleared_by_empty_highlight(qapp):
    from zlog.ui.log_model import MATCH_SPANS_ROLE

    model, _ = _wire(qapp)
    model.append_entries([_entry(message="a boom here")])
    model.set_highlight("boom")
    model.set_highlight("")
    spans = model.data(model.index(0, 0), MATCH_SPANS_ROLE)
    assert spans == []


def test_tag_color_beats_highlight(qapp):
    from PySide6.QtCore import Qt

    model, _ = _wire(qapp)
    model.set_highlight_color("#111111")
    model.set_tag_color("Tag", "#abcdef")
    model.append_entries([_entry(tag="Tag", message="boom")])
    model.set_highlight("boom")
    bg = model.data(model.index(0, 0), Qt.BackgroundRole)
    assert bg.name() == "#abcdef"


def test_time_mode_since_start(qapp):
    from PySide6.QtCore import Qt

    model, _ = _wire(qapp)
    model.append_entries(
        [
            LogEntry("06-30 12:00:00.000", "1", "1", "I", "T", "a"),
            LogEntry("06-30 12:00:01.500", "1", "1", "I", "T", "b"),
        ]
    )
    model.set_time_mode("since_start")
    assert model.data(model.index(0, 0), Qt.DisplayRole) == "+0.000"
    assert model.data(model.index(1, 0), Qt.DisplayRole) == "+1.500"


def test_time_mode_delta(qapp):
    from PySide6.QtCore import Qt

    model, _ = _wire(qapp)
    model.append_entries(
        [
            LogEntry("06-30 12:00:00.000", "1", "1", "I", "T", "a"),
            LogEntry("06-30 12:00:00.250", "1", "1", "I", "T", "b"),
            LogEntry("06-30 12:00:02.250", "1", "1", "I", "T", "c"),
        ]
    )
    model.set_time_mode("delta")
    assert model.data(model.index(0, 0), Qt.DisplayRole) == "+0.000"
    assert model.data(model.index(1, 0), Qt.DisplayRole) == "+0.250"
    assert model.data(model.index(2, 0), Qt.DisplayRole) == "+2.000"


def test_time_mode_absolute_is_raw(qapp):
    from PySide6.QtCore import Qt

    model, _ = _wire(qapp)
    model.append_entries([LogEntry("06-30 12:00:00.000", "1", "1", "I", "T", "a")])
    assert model.data(model.index(0, 0), Qt.DisplayRole) == "06-30 12:00:00.000"


def test_time_mode_unparsed_line_falls_back(qapp):
    from PySide6.QtCore import Qt

    model, _ = _wire(qapp)
    model.append_entries([LogEntry("", "", "", "", "", "--- beginning of main")])
    model.set_time_mode("since_start")
    assert model.data(model.index(0, 0), Qt.DisplayRole) == ""  # raw (empty) stamp


def test_exclude_hides_matching(qapp):
    model, proxy = _wire(qapp)
    model.append_entries([_entry(message="noise from GnssHal"), _entry(message="real error")])
    proxy.set_exclude("GnssHal")
    assert _messages(model, proxy) == ["real error"]


def test_exclude_empty_shows_all(qapp):
    model, proxy = _wire(qapp)
    model.append_entries([_entry(message="a"), _entry(message="b")])
    proxy.set_exclude("a")
    proxy.set_exclude("")
    assert len(_messages(model, proxy)) == 2


def test_exclude_invalid_regex_keeps_previous(qapp):
    model, proxy = _wire(qapp)
    model.append_entries([_entry(message="keep"), _entry(message="drop this")])
    assert proxy.set_exclude("drop", regex=True) is True
    assert _messages(model, proxy) == ["keep"]
    assert proxy.set_exclude("(bad", regex=True) is False
    assert _messages(model, proxy) == ["keep"]  # previous exclude retained


def test_exclude_combines_with_search(qapp):
    model, proxy = _wire(qapp)
    model.append_entries(
        [
            _entry(message="error in GnssHal"),
            _entry(message="error in app"),
            _entry(message="info in app"),
        ]
    )
    proxy.set_search("error", regex=False)
    proxy.set_exclude("GnssHal")
    assert _messages(model, proxy) == ["error in app"]


def test_highlight_rule_colors_matching_row(qapp):
    from PySide6.QtCore import Qt

    model, _ = _wire(qapp)
    model.append_entries([_entry(message="boom happened"), _entry(message="all quiet")])
    model.set_highlight_rules([{"pattern": "boom", "regex": False, "color": "#ff0000"}])
    hit = model.data(model.index(0, 0), Qt.BackgroundRole)
    miss = model.data(model.index(1, 0), Qt.BackgroundRole)
    assert hit is not None and hit.name() == "#ff0000"
    assert miss is None or miss.name() != "#ff0000"


def test_highlight_rule_loses_to_explicit_tag_color(qapp):
    from PySide6.QtCore import Qt

    model, _ = _wire(qapp)
    model.append_entries([_entry(tag="Foo", message="boom")])
    model.set_highlight_rules([{"pattern": "boom", "regex": False, "color": "#ff0000"}])
    model.set_tag_color("Foo", "#00ff00")
    color = model.data(model.index(0, 0), Qt.BackgroundRole)
    assert color.name() == "#00ff00"


def test_highlight_rule_first_match_wins(qapp):
    from PySide6.QtCore import Qt

    model, _ = _wire(qapp)
    model.append_entries([_entry(message="boom")])
    model.set_highlight_rules(
        [
            {"pattern": "boom", "regex": False, "color": "#ff0000"},
            {"pattern": "oo", "regex": False, "color": "#00ff00"},
        ]
    )
    color = model.data(model.index(0, 0), Qt.BackgroundRole)
    assert color.name() == "#ff0000"


def test_highlight_rule_shows_regardless_of_active_search(qapp):
    from PySide6.QtCore import Qt

    model, proxy = _wire(qapp)
    model.append_entries([_entry(message="boom")])
    model.set_highlight_rules([{"pattern": "boom", "regex": False, "color": "#ff0000"}])
    proxy.set_search("something else entirely", regex=False)
    color = model.data(model.index(0, 0), Qt.BackgroundRole)
    assert color.name() == "#ff0000"


def test_highlight_rule_invalid_regex_is_skipped_not_raised(qapp):
    model, _ = _wire(qapp)
    model.append_entries([_entry(message="boom")])
    model.set_highlight_rules([{"pattern": "(unclosed", "regex": True, "color": "#ff0000"}])
    assert model.highlight_rules() == []


def test_highlight_rules_round_trip(qapp):
    model, _ = _wire(qapp)
    rules = [{"pattern": "boom", "regex": False, "color": "#ff0000"}]
    model.set_highlight_rules(rules)
    assert model.highlight_rules() == rules


def test_bookmark_toggle_and_decoration(qapp):
    from PySide6.QtCore import Qt

    model, _ = _wire(qapp)
    model.set_bookmark_color("#abcdef")
    model.append_entries([_entry(message="a"), _entry(message="b")])
    assert model.is_bookmarked(1) is False
    model.toggle_bookmark(1)
    assert model.is_bookmarked(1) is True
    assert model.bookmarked_rows() == [1]
    deco = model.data(model.index(1, 0), Qt.DecorationRole)
    assert deco is not None and deco.name() == "#abcdef"
    assert model.data(model.index(0, 0), Qt.DecorationRole) is None
    model.toggle_bookmark(1)
    assert model.is_bookmarked(1) is False


def test_incident_tracking(qapp):
    model, _ = _wire(qapp)
    model.append_entries(
        [
            _entry(level="I", message="ordinary line"),
            _entry(level="E", tag="AndroidRuntime", message="FATAL EXCEPTION: main"),
            _entry(level="E", tag="ActivityManager", message="ANR in com.example (input)"),
        ]
    )
    assert model.incident_rows() == [1, 2]
    assert model.incident_counts() == {"crash": 1, "anr": 1}


def test_max_rows_remaps_incidents(qapp):
    model, _ = _wire(qapp)
    model.append_entries([_entry(message=str(i)) for i in range(2)])
    model.append_entries([_entry(message="FATAL EXCEPTION: main")])  # row 2
    model.set_max_rows(3)
    model.append_entries([_entry(message="3"), _entry(message="4")])  # 5 rows -> drop 2
    assert model.incident_rows() == [0]  # original row 2 shifted down to 0
    assert model.entry_at(0).message == "FATAL EXCEPTION: main"


def test_clear_bookmarks(qapp):
    model, _ = _wire(qapp)
    model.append_entries([_entry(), _entry()])
    model.toggle_bookmark(0)
    model.toggle_bookmark(1)
    model.clear_bookmarks()
    assert model.bookmarked_rows() == []


def test_clear_log_clears_bookmarks(qapp):
    model, _ = _wire(qapp)
    model.append_entries([_entry()])
    model.toggle_bookmark(0)
    model.clear()
    assert model.bookmarked_rows() == []


def test_clear_log_clears_incidents(qapp):
    model, _ = _wire(qapp)
    model.append_entries([_entry(message="FATAL EXCEPTION: main")])
    model.clear()
    assert model.incident_rows() == []


def test_max_rows_trims_to_last_n(qapp):
    model, _ = _wire(qapp)
    model.set_max_rows(3)
    model.append_entries([_entry(message=str(i)) for i in range(5)])
    assert model.rowCount() == 3
    assert [model.entry_at(r).message for r in range(3)] == ["2", "3", "4"]


def test_max_rows_zero_is_unlimited(qapp):
    model, _ = _wire(qapp)
    model.set_max_rows(0)
    model.append_entries([_entry() for _ in range(10)])
    assert model.rowCount() == 10


def test_set_max_rows_trims_existing_rows(qapp):
    model, _ = _wire(qapp)
    model.append_entries([_entry(message=str(i)) for i in range(6)])
    model.set_max_rows(2)
    assert model.rowCount() == 2
    assert [model.entry_at(r).message for r in range(2)] == ["4", "5"]


def test_max_rows_decrements_counts_for_dropped(qapp):
    model, _ = _wire(qapp)
    model.set_max_rows(2)
    model.append_entries(
        [_entry(level="E"), _entry(level="E"), _entry(level="W"), _entry(level="W")]
    )
    counts = model.level_counts()
    assert model.rowCount() == 2
    assert counts.get("E") is None  # both E rows trimmed away
    assert counts.get("W") == 2


def test_max_rows_remaps_bookmarks(qapp):
    model, _ = _wire(qapp)
    model.append_entries([_entry(message=str(i)) for i in range(3)])
    model.toggle_bookmark(2)  # bookmark the 3rd row (message "2")
    model.set_max_rows(3)
    model.append_entries([_entry(message="3"), _entry(message="4")])  # 5 rows -> drop 2
    assert model.bookmarked_rows() == [0]  # original row 2 shifted down to 0
    assert model.entry_at(0).message == "2"


def test_collapse_hides_consecutive_duplicates(qapp):
    model, proxy = _wire(qapp)
    a = _entry(level="I", tag="T", message="same")
    b = _entry(level="I", tag="T", message="other")
    model.append_entries([a, a, b, a])  # A A B A
    assert proxy.rowCount() == 4  # off by default
    proxy.set_collapse(True)
    # row1 (dup of row0) folds; row2 (B) and row3 (A, after B) stay
    assert proxy.rowCount() == 3
    assert _messages(model, proxy) == ["same", "other", "same"]
    proxy.set_collapse(False)
    assert proxy.rowCount() == 4


def test_collapse_first_row_always_shows(qapp):
    model, proxy = _wire(qapp)
    model.append_entries([_entry(message="x"), _entry(message="x")])
    proxy.set_collapse(True)
    assert proxy.rowCount() == 1  # the very first row is never folded


def test_colorizer_tints_row(qapp):
    from PySide6.QtGui import QColor

    from zlog.ui.log_model import HIGHLIGHT_ROLE

    model, _ = _wire(qapp)
    model.append_entries([_entry(level="E", message="boom")])
    model.set_colorizers([lambda e: "#123456" if e.level == "E" else None])
    color = model.data(model.index(0, 0), HIGHLIGHT_ROLE)
    assert isinstance(color, QColor) and color.name() == "#123456"


def test_process_role_and_start_proc_merge(qapp):
    from zlog.ui.log_model import PROCESS_ROLE

    model, proxy = _wire(qapp)
    model.append_entries(
        [
            _entry(message="Start proc 4921:com.android.systemui/u0a1 for x", pid="4921"),
            _entry(message="onExpansionChanged", pid="4921"),
        ]
    )
    # The Start proc line taught the model that PID 4921 -> com.android.systemui,
    # so every row from that PID resolves the name via PROCESS_ROLE.
    idx = model.index(1, 0)
    assert model.data(idx, PROCESS_ROLE) == "com.android.systemui"


def test_merge_process_names_from_snapshot(qapp):
    from zlog.ui.log_model import PROCESS_ROLE

    model, proxy = _wire(qapp)
    model.append_entries([_entry(pid="777")])
    assert model.data(model.index(0, 0), PROCESS_ROLE) == ""  # unknown yet
    model.merge_process_names({"777": "com.example.app"})
    assert model.data(model.index(0, 0), PROCESS_ROLE) == "com.example.app"


def test_clear_keeps_process_names(qapp):
    # Clearing the view (e.g. Clear device buffer) must NOT forget the pid->name
    # map — the processes are still running, so the package column should persist.
    model, proxy = _wire(qapp)
    model.merge_process_names({"1": "init"})
    model.clear()
    assert model.process_name("1") == "init"


def test_clear_process_names_forgets_map(qapp):
    # The offline-load path explicitly drops the map (PIDs are from another capture).
    model, proxy = _wire(qapp)
    model.merge_process_names({"1": "init"})
    model.clear_process_names()
    assert model.process_name("1") == ""


def test_query_pid_gate(qapp):
    model, proxy = _wire(qapp)
    model.append_entries([_entry(pid="100", message="a"), _entry(pid="200", message="b")])
    proxy.set_query_pids({"100"})
    assert _messages(model, proxy) == ["a"]
    proxy.set_query_pids(None)
    assert _messages(model, proxy) == ["a", "b"]


def test_proc_name_gate(qapp):
    model, proxy = _wire(qapp)
    model.append_entries([_entry(pid="100", message="sysui"), _entry(pid="200", message="other")])
    model.merge_process_names({"100": "com.android.systemui"})
    proxy.set_proc("systemui")
    assert _messages(model, proxy) == ["sysui"]  # only PID 100's resolved name matches
    proxy.set_proc("")
    assert _messages(model, proxy) == ["sysui", "other"]


def test_exclude_pid_gate(qapp):
    model, proxy = _wire(qapp)
    model.append_entries([_entry(pid="100", message="a"), _entry(pid="200", message="b")])
    proxy.set_exclude_pids({"100"})
    assert _messages(model, proxy) == ["b"]
    proxy.set_exclude_pids(None)
    assert _messages(model, proxy) == ["a", "b"]


def test_time_range_gate(qapp):
    from datetime import time

    model, proxy = _wire(qapp)
    model.append_entries(
        [
            LogEntry("06-30 10:00:00.000", "100", "200", "I", "Tag", "early"),
            LogEntry("06-30 11:00:00.000", "100", "200", "I", "Tag", "mid"),
            LogEntry("06-30 12:00:00.000", "100", "200", "I", "Tag", "late"),
        ]
    )
    proxy.set_time_range(time(10, 30, 0), time(11, 30, 0))
    assert _messages(model, proxy) == ["mid"]
    proxy.set_time_range(None, None)
    assert _messages(model, proxy) == ["early", "mid", "late"]


def test_time_range_gate_unparseable_stamp_always_passes(qapp):
    from datetime import time

    model, proxy = _wire(qapp)
    model.append_entries([_entry(message="banner")])  # default stamp has no MM-DD
    proxy.set_time_range(time(10, 0, 0), time(11, 0, 0))
    assert _messages(model, proxy) == ["banner"]


def test_exclude_proc_gate(qapp):
    model, proxy = _wire(qapp)
    model.append_entries([_entry(pid="100", message="sysui"), _entry(pid="200", message="other")])
    model.merge_process_names({"100": "com.android.systemui"})
    proxy.set_exclude_proc("systemui")
    assert _messages(model, proxy) == ["other"]  # PID 100's resolved name is excluded
    proxy.set_exclude_proc("")
    assert _messages(model, proxy) == ["sysui", "other"]
