"""Attaching and detaching readers for a capture session.

Every capture — adb logcat, a merged multi-device view, Windows debug output, a
launched app — is "a reader whose batches belong to one `LogSession`". Before
this, each start path re-did the same four steps by hand (connect the signals,
set the session fields, remember extra readers, stop them all again), which is
where the duplication (and the easy-to-forget `stream_ended` connection) lived.

Deliberately **widget-free**, like `DeviceController`: it wires signals to
callbacks the window supplies and mutates `LogSession` state, but never touches a
widget. That keeps the tab label and toolbar updates in the window, and lets this
unit-test with a stub reader and a bare session.
"""

from __future__ import annotations

from PySide6.QtCore import QObject


class CaptureController(QObject):
    def __init__(self, on_batch, on_error, on_stream_ended=None, parent=None):
        """`on_batch(sess, entries)` / `on_error(msg)` / `on_stream_ended(sess)`
        are the window's slots; keeping them as callbacks is what keeps this class
        free of widget knowledge."""
        super().__init__(parent)
        self._on_batch = on_batch
        self._on_error = on_error
        self._on_stream_ended = on_stream_ended
        # Readers that feed the *same* session alongside its primary one: the
        # merged multi-device view, and the DBWIN capture that accompanies a
        # launched app. Kept here so detach() can never miss one.
        self.extra_readers: list = []

    def attach(
        self,
        sess,
        reader,
        *,
        primary: bool = True,
        serial: str = "",
        stream_label: str = "",
        track_end: bool = False,
        on_end=None,
        on_error=None,
        start: bool = True,
    ):
        """Wire `reader` to `sess` and start it.

        `primary` readers become `sess.reader` (what Stop/pause act on); extras are
        remembered for teardown only. The `x=sess` default-argument binding pins
        each reader to its own session — without it every tab's batches would land
        in whichever session happened to be active when the signal fired.

        `on_end`/`on_error` override the window-wide slots for one reader: a
        launched app that exits isn't a device drop to reconnect to, and a
        contended DBWIN companion must not tear down the capture it accompanies.
        """
        reader.batch_ready.connect(lambda e, x=sess: self._on_batch(x, e))
        reader.error.connect(on_error or self._on_error)
        end = on_end if on_end is not None else (self._on_stream_ended if track_end else None)
        if end is not None:
            reader.stream_ended.connect(lambda x=sess: end(x))
        if start:
            reader.start()
        if primary:
            sess.reader = reader
            sess.serial = serial
            sess.title = ""  # a live stream owns the label; drop any loaded-file name
            sess.stream_label = stream_label
            sess.paused = False
            sess.pause_buffer = []
        else:
            self.extra_readers.append(reader)
        return reader

    def detach(self, sess) -> None:
        """Stop the session's primary reader *and* every extra, and clear the
        session's streaming state. Missing an extra here would leak a thread (or a
        launched child process), so both are torn down in one place."""
        if sess.reader:
            sess.reader.stop()
            sess.reader = None
        for reader in self.extra_readers:
            reader.stop()
        self.extra_readers = []
        sess.stream_label = ""
        sess.paused = False
        sess.pause_buffer = []

    @property
    def streaming(self) -> bool:
        """Whether any extra reader is running (the merged view's test for 'busy')."""
        return bool(self.extra_readers)
