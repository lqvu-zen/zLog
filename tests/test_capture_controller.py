"""Reader attach/detach, tested without a MainWindow.

The controller is deliberately widget-free, so a stub reader and a bare
LogSession are enough — no adb, no Windows, no window construction.
"""

from __future__ import annotations

import pytest
from PySide6.QtCore import QObject, Signal

from zlog.ui.capture_controller import CaptureController
from zlog.ui.log_session import LogSession


class StubReader(QObject):
    """Same signal surface as AdbReader / DebugOutputReader / LaunchReader."""

    batch_ready = Signal(list)
    error = Signal(str)
    stream_ended = Signal()

    def __init__(self):
        super().__init__()
        self.started = False
        self.stopped = False

    def start(self):
        self.started = True

    def stop(self):
        self.stopped = True


@pytest.fixture
def ctl(qapp):
    calls = {"batches": [], "errors": [], "ended": []}
    c = CaptureController(
        lambda sess, entries: calls["batches"].append((sess, entries)),
        lambda msg: calls["errors"].append(msg),
        lambda sess: calls["ended"].append(sess),
    )
    return c, calls


@pytest.fixture
def sess(qapp):
    return LogSession(None)


def test_attach_starts_and_sets_primary(ctl, sess):
    c, _ = ctl
    r = StubReader()
    c.attach(sess, r, serial="emulator-5554")
    assert r.started is True
    assert sess.reader is r
    assert sess.serial == "emulator-5554"
    assert c.extra_readers == []


def test_attach_routes_batches_to_its_session(ctl, sess):
    c, calls = ctl
    r = StubReader()
    c.attach(sess, r)
    r.batch_ready.emit(["a", "b"])
    assert calls["batches"] == [(sess, ["a", "b"])]


def test_each_reader_is_pinned_to_its_own_session(ctl, qapp):
    """The x=sess default-arg binding — without it both readers would report
    whichever session was bound last."""
    c, calls = ctl
    s1, s2 = LogSession(None), LogSession(None)
    r1, r2 = StubReader(), StubReader()
    c.attach(s1, r1)
    c.attach(s2, r2)
    r1.batch_ready.emit(["from 1"])
    r2.batch_ready.emit(["from 2"])
    assert calls["batches"] == [(s1, ["from 1"]), (s2, ["from 2"])]


def test_attach_clears_stale_session_state(ctl, sess):
    c, _ = ctl
    sess.title = "old.log"
    sess.paused = True
    sess.pause_buffer = ["stale"]
    c.attach(sess, StubReader(), stream_label="Debug Output")
    assert sess.title == ""  # a live stream owns the label
    assert sess.stream_label == "Debug Output"
    assert sess.paused is False and sess.pause_buffer == []


def test_non_primary_goes_to_extras(ctl, sess):
    c, _ = ctl
    r = StubReader()
    c.attach(sess, r, primary=False)
    assert sess.reader is None
    assert c.extra_readers == [r]
    assert c.streaming is True


def test_error_reaches_the_window_slot(ctl, sess):
    c, calls = ctl
    r = StubReader()
    c.attach(sess, r)
    r.error.emit("boom")
    assert calls["errors"] == ["boom"]


def test_error_override_bypasses_the_window_slot(ctl, sess):
    """A contended DBWIN companion must not tear down the capture it accompanies."""
    c, calls = ctl
    seen: list[str] = []
    c.attach(sess, r := StubReader(), primary=False, on_error=seen.append)
    r.error.emit("buffer busy")
    assert seen == ["buffer busy"]
    assert calls["errors"] == []


def test_stream_ended_only_when_tracked(ctl, sess):
    c, calls = ctl
    r = StubReader()
    c.attach(sess, r)  # track_end defaults False
    r.stream_ended.emit()
    assert calls["ended"] == []

    r2 = StubReader()
    c.attach(sess, r2, track_end=True)
    r2.stream_ended.emit()
    assert calls["ended"] == [sess]


def test_stream_ended_override(ctl, sess):
    """A launched app exiting isn't a device drop to reconnect to."""
    c, calls = ctl
    seen: list = []
    c.attach(sess, r := StubReader(), on_end=seen.append)
    r.stream_ended.emit()
    assert seen == [sess]
    assert calls["ended"] == []


def test_detach_stops_primary_and_extras(ctl, sess):
    c, _ = ctl
    primary, extra1, extra2 = StubReader(), StubReader(), StubReader()
    c.attach(sess, primary)
    c.attach(sess, extra1, primary=False)
    c.attach(sess, extra2, primary=False)

    c.detach(sess)

    assert primary.stopped and extra1.stopped and extra2.stopped  # nothing leaks
    assert sess.reader is None
    assert c.extra_readers == []
    assert c.streaming is False
    assert sess.stream_label == "" and sess.paused is False


def test_detach_is_safe_with_no_reader(ctl, sess):
    c, _ = ctl
    c.detach(sess)  # must not raise
    assert sess.reader is None
