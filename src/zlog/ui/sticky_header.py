"""A one-line strip pinned to the top of the log viewport, showing the current
anchor row (see `core.anchor`). It paints with the *same* delegate as the log so
it looks identical to a real row; clicking it scrolls back to that row.
"""

from __future__ import annotations

from PySide6.QtCore import QModelIndex, QRect, Qt, Signal
from PySide6.QtGui import QFontMetrics
from PySide6.QtWidgets import QStyleOptionViewItem, QWidget


class StickyHeader(QWidget):
    clicked = Signal()  # the strip was clicked (window scrolls to the anchor)

    def __init__(self, view, delegate, parent=None):
        super().__init__(parent or view.viewport())
        self._view = view
        self._delegate = delegate
        self._index = QModelIndex()  # the (proxy) index to render, or invalid → hidden
        self.setCursor(Qt.PointingHandCursor)
        self.hide()

    def row_height(self) -> int:
        return QFontMetrics(self._view.font()).height() + 4

    def set_index(self, index) -> None:
        """Show `index` (a proxy index) as the pinned line, or hide if invalid."""
        if index is None or not index.isValid():
            self._index = QModelIndex()
            self.hide()
            return
        self._index = index
        self.setFixedHeight(self.row_height())
        self.setFixedWidth(self._view.viewport().width())
        self.move(0, 0)
        self.show()
        self.raise_()
        self.update()

    def paintEvent(self, event) -> None:
        if not self._index.isValid():
            return
        from PySide6.QtGui import QPainter

        painter = QPainter(self)
        opt = QStyleOptionViewItem()
        opt.rect = QRect(0, 0, self.width(), self.height())
        opt.font = self._view.font()
        opt.state = QStyleOptionViewItem.State_None  # never draw a selection/hover tint
        self._delegate.paint(painter, opt, self._index)
        # a hairline under the strip to separate it from the scrolling rows
        painter.setPen(self._delegate._muted)
        painter.drawLine(0, self.height() - 1, self.width(), self.height() - 1)
        painter.end()

    def mousePressEvent(self, event) -> None:
        if self._index.isValid():
            self.clicked.emit()
