"""A vertical scrollbar that paints error-position ticks (a severity minimap).

MainWindow feeds it the fractional positions of error/fatal rows; we draw the
native scrollbar first, then thin ticks on top.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QScrollBar


class HeatScrollBar(QScrollBar):
    def __init__(self, parent=None):
        super().__init__(Qt.Vertical, parent)
        self._marks: list[float] = []  # positions 0..1
        self._color = QColor("#c62828")

    def set_marks(self, marks: list[float], color: str) -> None:
        self._marks = marks
        self._color = QColor(color)
        self.update()

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        if not self._marks:
            return
        painter = QPainter(self)
        h = self.height()
        w = self.width()
        span = max(0, h - 2)
        for frac in self._marks:
            y = int(frac * span)
            painter.fillRect(2, y, max(1, w - 4), 2, self._color)
        painter.end()
