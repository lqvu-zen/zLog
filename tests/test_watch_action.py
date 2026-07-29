from zlog.core.models import LogEntry
from zlog.core.watch_action import expand_command


def _entry(**overrides) -> LogEntry:
    fields = dict(
        time="06-30 12:34:56.789",
        pid="123",
        tid="456",
        level="E",
        tag="MyTag",
        message="boom",
    )
    fields.update(overrides)
    return LogEntry(**fields)


def test_empty_template_yields_no_command():
    assert expand_command("", _entry()) == []
    assert expand_command("   ", _entry()) == []


def test_substitutes_known_placeholders():
    entry = _entry(tag="Crash", message="oh no", pid="42", level="F")
    argv = expand_command("notify {tag} {message} pid={pid} lvl={level}", entry)
    assert argv == ["notify", "Crash", "oh no", "pid=42", "lvl=F"]


def test_unknown_placeholder_left_literal():
    argv = expand_command("run {oops}", _entry())
    assert argv == ["run", "{oops}"]


def test_line_placeholder_contains_full_entry():
    entry = _entry(tag="T", message="hello world")
    argv = expand_command("echo {line}", entry)
    assert argv == ["echo", "06-30 12:34:56.789 123-456 T E hello world"]


def test_shell_metacharacters_in_message_stay_one_argument():
    entry = _entry(message='x"; rm -rf ~; echo "')
    argv = expand_command("echo {message}", entry)
    assert argv == ["echo", 'x"; rm -rf ~; echo "']
    assert len(argv) == 2


def test_semicolon_and_ampersand_do_not_split_argv():
    entry = _entry(message="a && b; c | d")
    argv = expand_command("echo {message}", entry)
    assert argv == ["echo", "a && b; c | d"]


def test_message_with_spaces_via_placeholder_is_one_token():
    entry = _entry(message="multiple words here")
    argv = expand_command("notify {message}", entry)
    assert argv == ["notify", "multiple words here"]


def test_template_quoting_groups_the_users_own_argv():
    # shlex groups a quoted span into one token; on Windows (posix=False,
    # matching launcher.build_argv) the quotes themselves are kept literal.
    import os

    entry = _entry(message="ignored")
    argv = expand_command('script.sh "fixed arg" {tag}', entry)
    expected_arg = "fixed arg" if os.name == "posix" else '"fixed arg"'
    assert argv == ["script.sh", expected_arg, entry.tag]
