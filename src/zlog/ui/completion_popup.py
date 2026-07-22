"""The completion popup's look: each row shows the value on the left and a dim
description on the right (like Android Studio's logcat filter suggestions).
"""

from __future__ import annotations

from PySide6.QtCore import QModelIndex, Qt
from PySide6.QtGui import QColor, QStandardItem, QStandardItemModel
from PySide6.QtWidgets import QStyle, QStyledItemDelegate

DESC_ROLE = int(Qt.UserRole) + 1  # the right-aligned description text


def build_model(suggestions: list[tuple[str, str]]) -> QStandardItemModel:
    """A single-column model where each item's text is the value and DESC_ROLE holds
    its description."""
    model = QStandardItemModel()
    for value, description in suggestions:
        item = QStandardItem(value)
        item.setData(description, DESC_ROLE)
        item.setEditable(False)
        model.appendRow(item)
    return model


class SuggestionDelegate(QStyledItemDelegate):
    def __init__(self, muted="#8a8a8a", parent=None):
        super().__init__(parent)
        self._muted = QColor(muted)

    def set_muted(self, color: str) -> None:
        self._muted = QColor(color)

    def paint(self, painter, option, index: QModelIndex) -> None:
        # Let the base draw the row background + the left (value) text/selection.
        super().paint(painter, option, index)
        desc = index.data(DESC_ROLE)
        if not desc:
            return
        painter.save()
        selected = bool(option.state & QStyle.State_Selected)
        painter.setPen(option.palette.highlightedText().color() if selected else self._muted)
        rect = option.rect.adjusted(0, 0, -8, 0)
        painter.drawText(rect, int(Qt.AlignRight | Qt.AlignVCenter), str(desc))
        painter.restore()

    def sizeHint(self, option, index):
        size = super().sizeHint(option, index)
        desc = index.data(DESC_ROLE)
        if desc:
            # reserve room for the value + a gap + the description
            fm = option.fontMetrics
            size.setWidth(size.width() + fm.horizontalAdvance(str(desc)) + 40)
        return size
