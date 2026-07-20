"""A chip bar that renders the query bar's active tokens as removable chips.

Pure view: it reads `token_spans(text)` to lay out one chip per token, and each
chip's × emits `remove_requested(start, end)` — the window slices that span out of
the query via `core.query.remove_span`. Removing by character span (not token key)
handles duplicates like `-a -b` correctly. Hidden when the query is empty.
"""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QWidget

from zlog.core.query import token_spans

_KIND_COLORS = {
    "level": "#e0a030",  # amber
    "tag": "#2aa198",  # teal
    "package": "#3f9142",  # green
    "proc": "#3f9142",  # green
    "pid": "#3b7dd8",  # blue
    "exclude": "#d0453b",  # red
    "regex": "#9b59b6",  # purple
    "time": "#8a7a4b",  # olive
    "word": "#7a7f87",  # gray
}


class FilterChipBar(QWidget):
    remove_requested = Signal(int, int)  # (start, end) span to drop from the query

    def __init__(self, parent=None):
        super().__init__(parent)
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(6, 2, 6, 2)
        self._layout.setSpacing(4)
        self._layout.addStretch(1)  # trailing stretch keeps chips left-aligned
        self.hide()

    def set_query(self, text: str) -> None:
        """Rebuild the chips from `text`; hide the bar when there are no tokens."""
        # Clear existing chips (everything except the trailing stretch).
        while self._layout.count() > 1:
            item = self._layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

        spans = token_spans(text)
        for start, end, kind in spans:
            chip = self._make_chip(text[start:end], kind, start, end)
            self._layout.insertWidget(self._layout.count() - 1, chip)
        self.setVisible(bool(spans))

    def _make_chip(self, label: str, kind: str, start: int, end: int) -> QWidget:
        chip = QFrame()
        chip.setObjectName("filterChip")
        color = _KIND_COLORS.get(kind, _KIND_COLORS["word"])
        chip.setStyleSheet(
            f"#filterChip {{ border: 1px solid {color}; border-radius: 8px; }}"
            f"#filterChip QLabel {{ color: {color}; }}"
        )
        row = QHBoxLayout(chip)
        row.setContentsMargins(6, 1, 2, 1)
        row.setSpacing(2)
        row.addWidget(QLabel(label))
        close = QPushButton("×")
        close.setFixedSize(16, 16)
        close.setFlat(True)
        close.setToolTip("Remove this filter")
        close.clicked.connect(lambda _=False, s=start, e=end: self.remove_requested.emit(s, e))
        row.addWidget(close)
        return chip
