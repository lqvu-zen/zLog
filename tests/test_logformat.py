"""Tests for core/logformat.py: pure, no Qt."""

from zlog.core.logformat import (
    _PROBE_LENGTH,
    LogFormat,
    _build_probe,
    aliases_to_text,
    apply_aliases,
    compile_formats,
    detect_format,
    formats_from_json,
    formats_to_json,
    parse_aliases_text,
    resolve_format,
    time_pattern,
)


def _fmt(name="F", pattern=r"^(?P<level>\w): (?P<message>.*)$", aliases=None, builtin=False):
    return LogFormat(name=name, pattern=pattern, level_aliases=aliases or {}, builtin=builtin)


# --- compile_formats ---


def test_compile_formats_skips_invalid_regex():
    good = _fmt("Good", r"^(?P<message>.*)$")
    bad = _fmt("Bad", r"^(unclosed")
    compiled = compile_formats([good, bad])
    assert [cf.format.name for cf in compiled] == ["Good"]


def test_compile_formats_preserves_order():
    a, b = _fmt("A"), _fmt("B")
    compiled = compile_formats([a, b])
    assert [cf.format.name for cf in compiled] == ["A", "B"]


# --- apply_aliases ---


def test_apply_aliases_uses_explicit_mapping():
    assert apply_aliases("ERROR", {"ERROR": "E"}) == "E"


def test_apply_aliases_passes_through_canonical_letter():
    assert apply_aliases("W", {}) == "W"


def test_apply_aliases_unmapped_unknown_token_is_unparsed():
    assert apply_aliases("WEIRD", {"ERROR": "E"}) == ""


def test_apply_aliases_never_guesses():
    # A token that merely contains a canonical letter must not partial-match.
    assert apply_aliases("WARNING", {}) == ""


# --- detect_format ---


def test_detect_format_picks_the_best_match():
    logcat = _fmt("logcat", r"^(?P<time>\d\d-\d\d) (?P<level>[VDIWEF]) (?P<message>.*)$")
    other = _fmt("other", r"^\[(?P<level>\w+)\] (?P<message>.*)$")
    compiled = compile_formats([logcat, other])
    lines = ["06-30 I hello", "06-30 E boom", "not a log line at all"]
    winner = detect_format(lines, compiled)
    assert winner is not None and winner.name == "logcat"


def test_detect_format_tie_returns_none():
    a = _fmt("A", r"^(?P<message>.*)$")
    b = _fmt("B", r"^(?P<message>.*)$")
    compiled = compile_formats([a, b])
    winner = detect_format(["any line"], compiled)
    assert winner is None


def test_detect_format_no_match_returns_none():
    compiled = compile_formats([_fmt("F", r"^NEVER$")])
    assert detect_format(["nope", "still nope"], compiled) is None


def test_detect_format_empty_sample_returns_none():
    compiled = compile_formats([_fmt("F", r"^(?P<message>.*)$")])
    assert detect_format([], compiled) is None


# --- resolve_format ---


def test_resolve_format_finds_by_name():
    formats = [_fmt("A"), _fmt("B")]
    assert resolve_format("B", formats) is formats[1]


def test_resolve_format_missing_name_returns_none():
    assert resolve_format("Ghost", [_fmt("A")]) is None


# --- alias text round-trip ---


def test_parse_aliases_text_basic():
    assert parse_aliases_text("ERROR=E\nWARN=W\n") == {"ERROR": "E", "WARN": "W"}


def test_parse_aliases_text_ignores_blank_and_malformed_lines():
    assert parse_aliases_text("\n  \nnoequalsign\nERROR=E\n") == {"ERROR": "E"}


def test_parse_aliases_text_uppercases_the_letter():
    assert parse_aliases_text("error=e") == {"error": "E"}


def test_aliases_to_text_round_trips():
    aliases = {"ERROR": "E", "WARN": "W"}
    assert parse_aliases_text(aliases_to_text(aliases)) == aliases


# --- JSON round-trip ---


def test_formats_to_json_excludes_builtins():
    builtin = _fmt("Builtin", builtin=True)
    user = _fmt("User")
    data = formats_to_json([builtin, user])
    assert [d["name"] for d in data] == ["User"]


def test_formats_json_round_trip_with_nasty_pattern():
    nasty = _fmt("Nasty", pattern=r'^(?P<message>[\\"\'\n\t]+)$', aliases={"E\\R": "E"})
    data = formats_to_json([nasty])
    restored = formats_from_json(data)
    assert restored == [nasty]


def test_formats_from_json_skips_malformed_entries():
    data = [
        {"name": "Good", "pattern": r"^(?P<message>.*)$", "level_aliases": {}},
        {"name": "", "pattern": "x"},  # blank name -> skipped
        {"pattern": "x"},  # missing name -> skipped
        {"name": "NoPattern"},  # missing pattern -> skipped
        "not even a dict",
    ]
    restored = formats_from_json(data)
    assert [f.name for f in restored] == ["Good"]


def test_formats_from_json_non_list_returns_empty():
    assert formats_from_json({"not": "a list"}) == []
    assert formats_from_json(None) == []


def test_formats_from_json_restored_entries_are_never_builtin():
    data = [{"name": "X", "pattern": "^(?P<message>.*)$", "level_aliases": {}}]
    assert formats_from_json(data)[0].builtin is False


# --- time_pattern / _build_probe ---


def test_time_pattern_returns_zero_for_invalid_regex():
    assert time_pattern(r"^(unclosed", ["a line"]) == 0.0


def test_time_pattern_returns_positive_duration_for_valid_regex():
    assert time_pattern(r"^(?P<message>.*)$", ["a line", "another line"]) > 0.0


def test_build_probe_seeds_from_a_literal_character_in_the_pattern():
    # A classic backtracking blowup needs the probe to actually contain the
    # character its quantifier is chasing — a generic filler wouldn't trigger
    # any backtracking at all for (a+)+.
    probe = _build_probe(r"^(a+)+$")
    assert probe == "a" * _PROBE_LENGTH + "!"


def test_build_probe_skips_escape_class_letters():
    # \d is a digit class, not the literal letter d -- must not be picked as
    # the repeat seed (it would prove nothing, same as a generic filler).
    probe = _build_probe(r"^\d+$")
    assert probe == "x" * _PROBE_LENGTH + "!"


def test_build_probe_falls_back_to_x_with_no_literal_characters():
    probe = _build_probe(r"^\d+\s+\w+$")
    assert probe == "x" * _PROBE_LENGTH + "!"


def test_time_pattern_catastrophic_pattern_is_much_slower_than_normal():
    # The actual regression this whole mechanism exists to catch: a
    # deliberately catastrophic pattern must time out noticeably slower than
    # an ordinary one, so the dialog's warning has a real signal to key off.
    catastrophic = time_pattern(r"^(a+)+$", [])
    normal = time_pattern(r"^(?P<message>.*)$", [])
    assert catastrophic > normal * 10
