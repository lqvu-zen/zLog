"""Running-process shaping and focus-query rewriting. Pure: no Qt, no OS calls."""

from __future__ import annotations

from zlog.core.procinfo import (
    ProcessInfo,
    focus_query,
    merge_candidates,
    sort_processes,
    strip_marker,
)

PROCS = [
    ProcessInfo(1200, "notepad.exe"),
    ProcessInfo(42, "Explorer.exe"),
    ProcessInfo(7, "myapp.exe"),
    ProcessInfo(3, "myapp.exe"),
]


def test_sort_is_case_insensitive_then_pid():
    assert [(p.name, p.pid) for p in sort_processes(PROCS)] == [
        ("Explorer.exe", 42),
        ("myapp.exe", 3),
        ("myapp.exe", 7),
        ("notepad.exe", 1200),
    ]


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


# --- merge_candidates / strip_marker (App box Load list) -------------------
def test_merge_dedupes_case_insensitively_and_sorts():
    log_names = ["com.example.app", "myapp.exe"]
    running = [ProcessInfo(7, "MyApp.exe"), ProcessInfo(8, "notepad.exe")]
    assert merge_candidates(log_names, running) == [
        "com.example.app",
        "myapp.exe ●",
        "notepad.exe",
    ]


def test_merge_marks_only_the_overlap():
    out = merge_candidates(["log-only"], [ProcessInfo(1, "running-only")])
    assert out == ["log-only", "running-only"]  # neither marked, neither shared


def test_merge_survives_either_side_empty():
    assert merge_candidates([], [ProcessInfo(1, "a.exe")]) == ["a.exe"]
    assert merge_candidates(["a.exe"], []) == ["a.exe"]
    assert merge_candidates([], []) == []


def test_strip_marker_round_trips():
    assert strip_marker("myapp.exe ●") == "myapp.exe"
    assert strip_marker("myapp.exe") == "myapp.exe"
    assert strip_marker("  myapp.exe ●  ") == "myapp.exe"
