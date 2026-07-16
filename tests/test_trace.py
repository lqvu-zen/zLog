"""Tests for stack-trace frame detection — pure, no Qt."""

from zlog.core.trace import frame_hint, is_stack_frame


def test_detects_at_frames():
    assert is_stack_frame("\tat android.app.ActivityThread.main(ActivityThread.java:8000)")
    assert is_stack_frame("    at com.example.Foo.bar(Foo.java:42)")


def test_detects_more_summary():
    assert is_stack_frame("\t... 27 more")
    assert is_stack_frame("    ... 3 more")


def test_ordinary_lines_are_not_frames():
    assert not is_stack_frame("FATAL EXCEPTION: main")
    assert not is_stack_frame("java.lang.RuntimeException: Unable to start activity")
    assert not is_stack_frame("Caused by: java.lang.NullPointerException")
    assert not is_stack_frame("battery at 42 percent")  # "at" mid-sentence, not a frame


def test_frame_hint_pluralizes():
    assert frame_hint(27) == "… 27 frames"
    assert frame_hint(1) == "… 1 frame"
