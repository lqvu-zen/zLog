"""A QLineEdit that tints recognized query tokens (level:/tag:/package:/… etc.).

Keeps every QLineEdit affordance (clear button, completer, Enter, error tint) and
just paints a translucent rounded rectangle behind each recognized token so the
filter's structure is visible at a glance. Token spans come from the pure
`core.query.token_spans`; positions are font-metric based and clipped to the
content rect, so they're exact for the common (non-scrolled) case.
"""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFontMetrics, QPainter
from PySide6.QtWidgets import QLineEdit, QStyle, QStyleOptionFrame

from zlog.core.query import token_spans

# Base colors per token kind; drawn translucent so they read on both themes.
_KIND_COLORS = {
    "level": "#e0a030",  # amber
    "tag": "#2aa198",  # teal
    "package": "#3f9142",  # green
    "proc": "#3f9142",  # green
    "pid": "#3b7dd8",  # blue
    "exclude": "#d0453b",  # red
    "regex": "#9b59b6",  # purple
    "time": "#8a7a4b",  # olive
}
_ALPHA = 70  # translucency of the token tint


class QueryLineEdit(QLineEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._colors = {k: QColor(v) for k, v in _KIND_COLORS.items()}
        for c in self._colors.values():
            c.setAlpha(_ALPHA)

    def _text_origin_x(self) -> int:
        """Left x where the text starts (content rect + QLineEdit's 2px margin)."""
        opt = QStyleOptionFrame()
        self.initStyleOption(opt)
        r = self.style().subElementRect(QStyle.SE_LineEditContents, opt, self)
        return r.left() + 2 + self.textMargins().left()

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        text = self.text()
        if not text:
            return
        spans = [(s, e, k) for s, e, k in token_spans(text) if k in self._colors]
        if not spans:
            return
        fm = QFontMetrics(self.font())
        opt = QStyleOptionFrame()
        self.initStyleOption(opt)
        content = self.style().subElementRect(QStyle.SE_LineEditContents, opt, self)
        origin = self._text_origin_x()
        top = content.top() + 1
        height = content.height() - 2
        painter = QPainter(self)
        painter.setClipRect(content)  # never spill past the box (e.g. clear button)
        painter.setPen(Qt.NoPen)
        for start, end, kind in spans:
            x0 = origin + fm.horizontalAdvance(text[:start])
            x1 = origin + fm.horizontalAdvance(text[:end])
            painter.setBrush(self._colors[kind])
            painter.drawRoundedRect(QRectF(x0 - 1, top, (x1 - x0) + 2, height), 3, 3)
        painter.end()
