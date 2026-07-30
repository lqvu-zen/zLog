"""A thin label strip above the log naming each segment of its dense,
one-line-per-entry rows.

The rows have no real Qt columns — `LogItemDelegate` paints "Time PID·TID Tag
▮Lvl Message" freehand into one stretched column at offsets it computes itself
(`_col_widths`/`_gutter_w`). This widget reuses those exact methods (same
delegate instance) rather than re-deriving parallel layout math, so the labels
can never drift out of alignment with the rows below them. Read-only — no
click-to-sort, no drag-to-resize, since there are no real column boundaries to
act on.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFontMetrics, QPainter
from PySide6.QtWidgets import QWidget

_HEIGHT_PAD = 6


class LogHeaderBar(QWidget):
    def __init__(self, delegate, model_provider, parent=None):
        """`delegate` is the window's single shared `LogItemDelegate`.
        `model_provider` is a zero-arg callable returning the *currently
        active* tab's `LogTableModel` (a plain reference would go stale the
        moment the user switches tabs)."""
        super().__init__(parent)
        self._delegate = delegate
        self._model_provider = model_provider
        self._text = QColor("#5f6368")
        self._bg = QColor("#f3f3f3")
        self._border = QColor("#888888")
        self.setFixedHeight(QFontMetrics(self.font()).height() + _HEIGHT_PAD)

    def set_theme(self, text: str, bg: str, border: str) -> None:
        self._text = QColor(text)
        self._bg = QColor(bg)
        self._border = QColor(border)
        self.update()

    def setFont(self, font) -> None:
        super().setFont(font)
        self.setFixedHeight(QFontMetrics(font).height() + _HEIGHT_PAD)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), self._bg)
        painter.setPen(self._border)
        painter.drawLine(0, self.height() - 1, self.width(), self.height() - 1)

        fm = QFontMetrics(self.font())
        painter.setFont(self.font())
        cw = fm.horizontalAdvance("M") or 8
        pad = self._delegate._pad
        model = self._model_provider()
        gutter = self._delegate._gutter_w(model, fm)
        left = gutter
        time_w, pid_w, tag_w, proc_w = self._delegate._col_widths(left, self.width(), cw, model, fm)

        x = left + pad
        rect_h = self.height() - 1  # leave the border line unpainted-over

        def label(text, width_px):
            nonlocal x
            w = int(max(width_px, 0))
            if w == 0:
                return  # mirrors log_delegate.seg(): auto-hidden segment, no draw, no gap
            painter.drawText(
                x,
                0,
                w,
                rect_h,
                int(Qt.AlignVCenter | Qt.AlignLeft),
                fm.elidedText(text, Qt.ElideRight, w),
            )
            x += w + cw

        painter.setPen(self._text)
        label("Time", time_w)
        label("PID·TID", pid_w)
        label("Tag", tag_w)
        if self._delegate.show_process:
            label("Process", proc_w)
        # Mirror the level chip's reserved space (2*cw box + 1*cw gap, i.e. a
        # 3*cw total advance, exactly like paint()'s `x += 3 * cw` after the
        # chip) — a plain "L" here (not "Lvl": the real chip is one glyph wide,
        # e.g. "I"/"W", and this 2-char box would just elide anything longer).
        label("L", 2 * cw)
        painter.drawText(
            x,
            0,
            max(0, self.width() - x - pad),
            rect_h,
            int(Qt.AlignVCenter | Qt.AlignLeft),
            "Message",
        )
        painter.end()
