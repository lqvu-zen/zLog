"""Tests for the pure query-bar completion brain (no Qt)."""

from zlog.core.completion import completions, current_token


def _values(sugg):
    return [v for v, _d in sugg]


def test_current_token_at_end_and_in_whitespace():
    assert current_token("level:E tag:Foo", 7) == (0, 7, "level:E")  # caret at end of token 1
    assert current_token("level:E ", 8) == (8, 8, "")  # caret after the space -> new token
    assert current_token("", 0) == (0, 0, "")


def test_current_token_quoted():
    t = 'tag:"My Tag" x'
    s, e, tok = current_token(t, 5)  # caret inside the quoted value
    assert tok == 'tag:"My Tag"' and (s, e) == (0, 12)


def test_bare_token_suggests_field_keys():
    _s, _e, sugg = completions("", 0)
    vals = _values(sugg)
    assert "level:" in vals and "tag:" in vals and "pid:" in vals and "proc:" in vals
    # typing "ta" narrows to tag:
    _s, _e, sugg = completions("ta", 2)
    assert _values(sugg) == ["tag:"]


def test_level_completion_with_descriptions_and_prefix():
    start, end, sugg = completions("level:", 6)
    assert (start, end) == (0, 6)
    vals = _values(sugg)
    assert "level:error" in vals and "level:verbose" in vals
    desc = dict(sugg)["level:error"]
    assert "or higher" in desc and "ERROR" in desc
    # prefix filters
    _s, _e, sugg = completions("level:er", 8)
    assert _values(sugg) == ["level:error"]


def test_tag_pid_proc_use_live_values():
    tags = ["ActivityManager", "Zygote"]
    _s, _e, sugg = completions("tag:Ac", 6, tags=tags)
    assert _values(sugg) == ["tag:ActivityManager"]

    _s, _e, sugg = completions("pid:1", 5, pids=["100", "1200", "3"])
    assert _values(sugg) == ["pid:100", "pid:1200"]  # prefix "pid:1"

    _s, _e, sugg = completions("proc:com", 8, procs=["com.example.app", "system_server"])
    assert _values(sugg) == ["proc:com.example.app"]


def test_tag_value_with_space_is_quoted():
    _s, _e, sugg = completions("tag:My", 6, tags=["My Tag"])
    assert _values(sugg) == ['tag:"My Tag"']


def test_exclude_prefix_suggests_negatable_keys():
    _s, _e, sugg = completions("-", 1)
    vals = _values(sugg)
    assert "-pid:" in vals and "-proc:" in vals and "-device:" in vals
    _s, _e, sugg = completions("-pi", 3)
    assert _values(sugg) == ["-pid:"]
