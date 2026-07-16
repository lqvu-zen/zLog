"""A QTableView that paints a centered placeholder when it has no visible rows.

QTableView has no built-in empty-state text, so we draw it in the viewport's
paint event. `MainWindow` sets the text from context (nothing captured vs.
filtered to nothing).
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPainter, QPalette
from PySide6.QtWidgets import QTableView

from zlog.ui.log_model import FOLD_ROLE


class LogTableView(QTableView):
    # Emitted with a source-model row when a stack-trace header is double-clicked.
    fold_toggle_requested = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._placeholder = ""

    def mouseDoubleClickEvent(self, event) -> None:
        index = self.indexAt(event.position().toPoint())
        if index.isValid() and index.data(FOLD_ROLE):
            model = self.model()
            src = model.mapToSource(index).row() if hasattr(model, "mapToSource") else index.row()
            self.fold_toggle_requested.emit(src)
            return  # don't let the double-click also start a selection/edit
        super().mouseDoubleClickEvent(event)

    def set_placeholder(self, text: str) -> None:
        if text != self._placeholder:
            self._placeholder = text
            self.viewport().update()

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        model = self.model()
        if self._placeholder and (model is None or model.rowCount() == 0):
            painter = QPainter(self.viewport())
            painter.setPen(self.palette().color(QPalette.PlaceholderText))
            painter.drawText(self.viewport().rect(), Qt.AlignCenter, self._placeholder)
            painter.end()
