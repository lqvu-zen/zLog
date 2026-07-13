"""A per-tab capture session: an independent model/proxy/reader stack plus its
streaming state.

`MainWindow` re-roots `model`/`proxy`/`reader`/pause/reconnect to the *active*
session (via properties), so a single window can hold several device streams in
tabs without threading the session through every method.
"""

from __future__ import annotations

from PySide6.QtCore import QTimer

from zlog.core.models import LogEntry
from zlog.ui.log_model import LogFilterProxy, LogTableModel


class LogSession:
    def __init__(self, parent):
        self.model = LogTableModel(parent)
        self.proxy = LogFilterProxy(parent)
        self.proxy.setSourceModel(self.model)
        self.reader = None
        self.serial = ""  # device this tab targets
        self.query = ""  # this tab's query-bar text
        self.paused = False
        self.pause_buffer: list[LogEntry] = []
        self.want_stream = False  # intends to stream (drives auto-reconnect)
        self.reconnect_serial = None
        self.last_time = ""  # last log timestamp seen (reconnect resume point)
        self.reconnect_timer = QTimer(parent)
        self.reconnect_timer.setInterval(2000)
