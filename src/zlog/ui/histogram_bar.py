"""A thin band that charts log volume (and error share) over the capture's time
span. MainWindow feeds it `Bucket`s from `core.histogram`; a click emits the
source row to seek to.
"""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QWidget

from zlog.core.histogram import Bucket

_HEIGHT = 30


class HistogramBar(QWidget):
    seek_requested = Signal(int)  # source-row index to scroll to

    def __init__(self, parent=None):
        super().__init__(parent)
        self._buckets: list[Bucket] = []
        self._bar = QColor("#6a6a6a")
        self._error = QColor("#c62828")
        self._bg = QColor("#f3f3f3")
        self.setFixedHeight(_HEIGHT)
        self.setToolTip("Log volume over time — click to jump")

    def set_theme(self, bar: str, error: str, bg: str) -> None:
        self._bar = QColor(bar)
        self._error = QColor(error)
        self._bg = QColor(bg)
        self.update()

    def set_data(self, buckets: list[Bucket]) -> None:
        self._buckets = buckets
        self.update()

    def bucket_count(self) -> int:
        """How many buckets fit the current width (one bar per ~4px)."""
        return max(1, self.width() // 4)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), self._bg)
        n = len(self._buckets)
        if n == 0:
            painter.end()
            return
        w = self.width()
        h = self.height()
        peak = max(b.count for b in self._buckets) or 1
        bar_w = max(1, w / n)
        for i, b in enumerate(self._buckets):
            if b.count == 0:
                continue
            x = int(i * bar_w)
            bw = max(1, int(bar_w))
            bar_h = int((b.count / peak) * (h - 2))
            y = h - bar_h
            painter.fillRect(x, y, bw, bar_h, self._bar)
            if b.error_count:
                err_h = int((b.error_count / b.count) * bar_h)
                painter.fillRect(x, h - err_h, bw, err_h, self._error)
        painter.end()

    def mousePressEvent(self, event) -> None:
        n = len(self._buckets)
        if n == 0 or self.width() <= 0:
            return
        idx = min(n - 1, max(0, int(event.position().x() / self.width() * n)))
        # Walk forward to the nearest non-empty bucket so a click in a gap still lands.
        for j in range(idx, n):
            if self._buckets[j].first_index >= 0:
                self.seek_requested.emit(self._buckets[j].first_index)
                return
        super().mousePressEvent(event)
