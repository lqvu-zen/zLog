"""Tests for the pure plugin loader / colorizer application. No Qt required."""

from zlog.core.models import LogEntry
from zlog.core.plugins import apply_colorizers, load_colorizers


def _entry(tag="T", message="m", level="I"):
    return LogEntry("t", "1", "2", level, tag, message)


def test_load_colorizers_finds_and_isolates_errors(tmp_path):
    (tmp_path / "good.py").write_text(
        "def colorize(entry):\n    return '#ff0000' if entry.level == 'E' else None\n",
        encoding="utf-8",
    )
    (tmp_path / "broken.py").write_text(
        "def colorize(entry): 1/0\nsyntax ??? error\n", encoding="utf-8"
    )
    (tmp_path / "_skip.py").write_text("def colorize(entry): return '#000'\n", encoding="utf-8")
    fns, errors = load_colorizers(str(tmp_path))
    assert len(fns) == 1  # good.py only; broken skipped, _skip ignored
    assert errors and "broken.py" in errors[0]


def test_apply_colorizers_first_non_none_and_swallows_raises():
    def raises(_):
        raise RuntimeError("boom")

    def none(_):
        return None

    def red(e):
        return "#ff0000"

    assert apply_colorizers([raises, none, red], _entry()) == "#ff0000"
    assert apply_colorizers([none], _entry()) is None
    assert apply_colorizers([], _entry()) is None


def test_missing_dir_is_empty():
    assert load_colorizers("/no/such/dir") == ([], [])
