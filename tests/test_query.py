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


def test_level_set():
    q = parse_query("level:W,E boom")
    assert q.levels == ("W", "E") and q.level is None and q.search == "boom"


def test_level_single_is_floor():
    q = parse_query("level:E")
    assert q.level == "E" and q.levels == ()


def test_level_full_name_lowercase():
    assert parse_query("level:verbose").level == "V"
    assert parse_query("level:debug").level == "D"
    assert parse_query("level:info").level == "I"
    assert parse_query("level:warn").level == "W"
    assert parse_query("level:warning").level == "W"
    assert parse_query("level:error").level == "E"
    assert parse_query("level:fatal").level == "F"


def test_level_full_name_uppercase_and_mixed_case():
    assert parse_query("level:ERROR").level == "E"
    assert parse_query("level:Error").level == "E"
    assert parse_query("level:WARNING").level == "W"
    assert parse_query("level:Warn").level == "W"


def test_level_full_name_comma_set():
    q = parse_query("level:error,warning boom")
    assert q.levels == ("E", "W") and q.level is None and q.search == "boom"


def test_level_full_name_mixed_with_letter():
    q = parse_query("level:E,warning")
    assert q.levels == ("E", "W") and q.level is None


def test_level_bad_full_name_ignored():
    q = parse_query("level:critical hello")
    assert q.level is None and q.search == "level:critical hello"


def test_parse_pid_single_and_set():
    assert parse_query("pid:4921").pids == ("4921",)
    assert parse_query("pid:100,200,100").pids == ("100", "200")  # deduped, order kept
    assert parse_query("pid:abc").pids == ()  # non-numeric ignored


def test_parse_proc_name():
    assert parse_query("proc:com.miui.securitycenter:ui").process == "com.miui.securitycenter:ui"
    assert parse_query("process:com.foo").process == "com.foo"


def test_pid_and_proc_coexist_with_search():
    spec = parse_query("pid:5 proc:com.x tag:Act boom")
    assert spec.pids == ("5",) and spec.process == "com.x"
    assert spec.tag == "Act" and spec.search == "boom"


def test_parse_exclude_pid_single_and_set():
    assert parse_query("-pid:4921").exclude_pids == ("4921",)
    assert parse_query("-pid:100,200,100").exclude_pids == ("100", "200")
    assert parse_query("-pid:abc").exclude_pids == ()  # non-numeric ignored, no crash


def test_parse_exclude_proc_name():
    assert parse_query("-proc:com.foo").exclude_process == "com.foo"
    assert parse_query("-process:com.bar").exclude_process == "com.bar"


def test_exclude_pid_proc_coexist_with_includes_and_generic_exclude():
    spec = parse_query("pid:5 -pid:6 proc:com.x -proc:com.y -noise boom")
    assert spec.pids == ("5",) and spec.exclude_pids == ("6",)
    assert spec.process == "com.x" and spec.exclude_process == "com.y"
    assert spec.excludes == ("noise",) and spec.search == "boom"


def test_parse_since_and_until():
    spec = parse_query("since:12:00:00 until:12:05:00")
    assert spec.since == "12:00:00" and spec.until == "12:05:00"


def test_since_until_coexist_with_other_tokens():
    spec = parse_query("since:12:00:00 tag:Act until:12:05:00 boom")
    assert spec.since == "12:00:00" and spec.until == "12:05:00"
    assert spec.tag == "Act" and spec.search == "boom"


def test_token_spans_classifies_since_and_until():
    from zlog.core.query import token_spans

    t = "since:12:00:00 until:12:05:00"
    kinds = {t[s:e]: k for s, e, k in token_spans(t)}
    assert kinds["since:12:00:00"] == "time"
    assert kinds["until:12:05:00"] == "time"


def test_token_spans_classifies_each_kind():
    from zlog.core.query import token_spans

    t = "level:E tag:Foo package:com.x pid:5 proc:com.y -noise /re/ plain"
    kinds = {t[s:e]: k for s, e, k in token_spans(t)}
    assert kinds["level:E"] == "level"
    assert kinds["tag:Foo"] == "tag"
    assert kinds["package:com.x"] == "package"
    assert kinds["pid:5"] == "pid"
    assert kinds["proc:com.y"] == "proc"
    assert kinds["-noise"] == "exclude"
    assert kinds["/re/"] == "regex"
    assert kinds["plain"] == "word"


def test_token_spans_keeps_quoted_value_as_one_token():
    from zlog.core.query import token_spans

    t = 'tag:"My Tag" boom'
    spans = token_spans(t)
    s, e, k = spans[0]
    assert t[s:e] == 'tag:"My Tag"' and k == "tag"
    assert spans[1][2] == "word"


def test_token_spans_unknown_key_is_word():
    from zlog.core.query import token_spans

    assert token_spans("foo:bar")[0][2] == "word"
