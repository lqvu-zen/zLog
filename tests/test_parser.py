"""Tests for the pure parsing layer. No Qt or display required."""

from zlog.core.logformat import LogFormat, compile_formats
from zlog.core.models import LogEntry
from zlog.core.parser import BUILTIN_LOG_FORMATS, parse_line


def test_parses_standard_threadtime_line():
    line = "06-30 12:34:56.789  1234  5678 I ActivityManager: Start proc"
    entry = parse_line(line)
    assert entry == LogEntry(
        time="06-30 12:34:56.789",
        pid="1234",
        tid="5678",
        level="I",
        tag="ActivityManager",
        message="Start proc",
    )


def test_level_rank_orders_severity():
    assert (
        parse_line("06-30 12:00:00.000 1 1 E Tag: boom").rank
        > parse_line("06-30 12:00:00.000 1 1 I Tag: ok").rank
    )


def test_unparsed_line_keeps_full_text_in_message():
    line = "--------- beginning of main"
    entry = parse_line(line)
    assert entry.level == ""
    assert entry.message == line
    assert entry.rank == 0


def test_tag_with_spaces_is_trimmed():
    entry = parse_line("06-30 12:34:56.789 1 1 W My Tag : something")
    assert entry.level == "W"
    assert entry.tag == "My Tag"
    assert entry.message == "something"


def test_empty_message_is_allowed():
    entry = parse_line("06-30 12:34:56.789 1 1 D Tag: ")
    assert entry.level == "D"
    assert entry.message == ""


def test_parses_time_format():
    entry = parse_line("06-30 12:34:56.789 I/ActivityManager(  1234): Start proc")
    assert entry == LogEntry(
        time="06-30 12:34:56.789",
        pid="1234",
        tid="",
        level="I",
        tag="ActivityManager",
        message="Start proc",
    )


def test_parses_brief_format():
    entry = parse_line("W/Choreographer(  456): Skipped 12 frames")
    assert entry.level == "W"
    assert entry.tag == "Choreographer"
    assert entry.pid == "456"
    assert entry.time == "" and entry.tid == ""
    assert entry.message == "Skipped 12 frames"


def test_parses_tag_format():
    entry = parse_line("E/AndroidRuntime: FATAL EXCEPTION")
    assert entry.level == "E"
    assert entry.tag == "AndroidRuntime"
    assert entry.pid == "" and entry.time == ""
    assert entry.message == "FATAL EXCEPTION"


def test_brief_wins_over_tag_for_pid_lines():
    # A (pid) line must parse as brief (pid recovered), not tag (which would
    # swallow "(456)" into the tag).
    entry = parse_line("I/Tag(  456): hi")
    assert entry.tag == "Tag" and entry.pid == "456" and entry.message == "hi"


# --- custom formats (formats=None must stay unchanged; see the four tests above) ---


def test_formats_none_is_byte_identical_to_default():
    line = "06-30 12:34:56.789  1234  5678 I ActivityManager: Start proc"
    assert parse_line(line, None) == parse_line(line)


def test_custom_format_populates_canonical_fields():
    fmt = LogFormat(
        name="MyProject",
        pattern=r"^(?P<time>\d+) (?P<level>\w+) (?P<tag>\w+): (?P<message>.*)$",
        level_aliases={"ERROR": "E", "WARN": "W"},
    )
    compiled = compile_formats([fmt])
    entry = parse_line("12345 ERROR Boom: it broke", compiled)
    assert entry.time == "12345"
    assert entry.level == "E"  # aliased
    assert entry.tag == "Boom"
    assert entry.message == "it broke"


def test_custom_format_unmapped_level_is_unparsed_not_guessed():
    fmt = LogFormat(
        name="MyProject",
        pattern=r"^(?P<level>\w+): (?P<message>.*)$",
        level_aliases={"ERROR": "E"},  # WARN deliberately not mapped
    )
    compiled = compile_formats([fmt])
    entry = parse_line("WARN: careful", compiled)
    assert entry.level == ""  # unmapped -> unparsed, never a guess


def test_builtins_tried_first_survive_a_greedy_user_format():
    # A user format that would swallow anything must not shadow logcat when
    # built-ins are listed first — the caller's responsibility per
    # docs/plans/custom-log-format-editor.md's ordering risk.
    greedy = LogFormat(name="Greedy", pattern=r"^(?P<message>.*)$", level_aliases={})
    compiled = compile_formats([*BUILTIN_LOG_FORMATS, greedy])
    line = "06-30 12:34:56.789  1234  5678 I ActivityManager: Start proc"
    entry = parse_line(line, compiled)
    assert entry.level == "I" and entry.tag == "ActivityManager"  # threadtime won, not Greedy


def test_no_format_matches_falls_back_to_raw_message():
    fmt = LogFormat(name="MyProject", pattern=r"^NEVER MATCHES$", level_aliases={})
    compiled = compile_formats([fmt])
    entry = parse_line("some ordinary line", compiled)
    assert entry.level == "" and entry.message == "some ordinary line"
