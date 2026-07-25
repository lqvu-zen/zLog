"""Process-picker shaping and focus-query rewriting. Pure: no Qt, no OS calls."""

from __future__ import annotations

from zlog.core.procinfo import ProcessInfo, filter_processes, focus_query, sort_processes

PROCS = [
    ProcessInfo(1200, "notepad.exe"),
    ProcessInfo(42, "Explorer.exe"),
    ProcessInfo(7, "myapp.exe"),
    ProcessInfo(3, "myapp.exe"),
]


def test_label():
    assert ProcessInfo(1234, "a.exe").label == "a.exe (1234)"


def test_sort_is_case_insensitive_then_pid():
    assert [(p.name, p.pid) for p in sort_processes(PROCS)] == [
        ("Explorer.exe", 42),
        ("myapp.exe", 3),
        ("myapp.exe", 7),
        ("notepad.exe", 1200),
    ]


def test_filter_by_name_case_insensitive():
    assert [p.pid for p in filter_processes(PROCS, "MYAPP")] == [7, 3]


def test_filter_by_pid_text():
    assert [p.pid for p in filter_processes(PROCS, "120")] == [1200]


def test_filter_empty_returns_all():
    assert len(filter_processes(PROCS, "  ")) == len(PROCS)


def test_focus_by_name_on_empty_query():
    assert focus_query("", name="myapp.exe") == "proc:myapp.exe"


def test_focus_by_pid():
    assert focus_query("", pid=1234) == "pid:1234"


def test_pid_wins_over_name():
    assert focus_query("", name="a.exe", pid=9) == "pid:9"


def test_focus_keeps_other_tokens():
    out = focus_query("level:E tag:Net -noise /re\\d/", name="app.exe")
    assert out == "level:E tag:Net -noise /re\\d/ proc:app.exe"


def test_focus_replaces_existing_focus_tokens():
    out = focus_query("proc:old.exe level:W pid:1 package:com.x", name="new.exe")
    assert out == "level:W proc:new.exe"


def test_focus_quotes_name_with_space():
    assert focus_query("", name="my app.exe") == 'proc:"my app.exe"'


def test_focus_clears_when_no_target():
    assert focus_query("proc:old.exe level:E") == "level:E"
