"""One-line-per-entry painter for the log view (Android-Studio-style).

Keeps the model virtualized: the view calls this only for visible rows, so a
million-line capture still renders cheaply. Segments are laid out at fixed
monospace offsets (a table-like alignment without a grid), with the message
tinted per level and a small colored level chip.
"""

from __future__ import annotations

from PySide6.QtCore import QRect, QSize, Qt
from PySide6.QtGui import QColor, QFontMetrics
from PySide6.QtWidgets import QStyle, QStyledItemDelegate

from zlog.ui.log_model import HIGHLIGHT_ROLE, PROCESS_ROLE

_TIME_W = 24  # fixed: fits the full 'YYYY-MM-DD HH:MM:SS.mmm' stamp, kept readable
_PIDTID_W = 12
_TAG_W = 22
_PROC_W = 30  # process/package column; longer names elide in the middle


class LogItemDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._muted = QColor("#888888")
        self._meta = QColor("#5f6368")  # time/pid/tag columns (readable metadata)
        self._level_text: dict[str, QColor] = {}
        self._chip_fg = QColor("#ffffff")
        self._sel_bg = QColor("#2b6cdb")
        self._sel_fg = QColor("#ffffff")
        self._hover_bg = QColor("#dbe9fb")
        self._pad = 6
        self.show_process = False  # paint the process/package column

    def set_theme(
        self,
        muted: str,
        meta: str,
        level_text: dict[str, str],
        chip_fg: str,
        selection_bg: str,
        selection_text: str,
        row_hover_bg: str,
    ) -> None:
        self._muted = QColor(muted)
        self._meta = QColor(meta)
        self._level_text = {k: QColor(v) for k, v in level_text.items()}
        self._chip_fg = QColor(chip_fg)
        self._sel_bg = QColor(selection_bg)
        self._sel_fg = QColor(selection_text)
        self._hover_bg = QColor(row_hover_bg)

    def sizeHint(self, option, index):
        return QSize(0, QFontMetrics(option.font).height() + 4)

    def paint(self, painter, option, index):
        painter.save()
        selected = bool(option.state & QStyle.State_Selected)
        hovered = bool(option.state & QStyle.State_MouseOver)
        if selected:
            painter.fillRect(option.rect, self._sel_bg)
        elif hovered:
            painter.fillRect(option.rect, self._hover_bg)
        else:
            bg = index.data(HIGHLIGHT_ROLE)
            if isinstance(bg, QColor):
                painter.fillRect(option.rect, bg)

        fm = QFontMetrics(option.font)
        cw = fm.horizontalAdvance("M") or 8
        top, height = option.rect.top(), option.rect.height()
        x = option.rect.left() + self._pad
        painter.setFont(option.font)

        deco = index.data(Qt.DecorationRole)
        if isinstance(deco, QColor):
            painter.fillRect(QRect(option.rect.left(), top + 2, 3, height - 4), deco)

        base_fg = self._sel_fg if selected else self._meta
        time_str = index.data(Qt.DisplayRole) or ""  # honors the Time display mode
        entry = index.data(Qt.UserRole)

        if entry is None or not entry.level:
            painter.setPen(base_fg)
            text = time_str if entry is None else entry.message
            painter.drawText(
                QRect(x, top, option.rect.right() - x - self._pad, height),
                int(Qt.AlignVCenter | Qt.AlignLeft),
                text,
            )
            painter.restore()
            return

        def seg(text, width_chars, color, elide=None):
            nonlocal x
            w = width_chars * cw
            s = text or ""
            if elide:
                mode = Qt.ElideMiddle if elide == "middle" else Qt.ElideRight
                s = fm.elidedText(s, mode, w)
            painter.setPen(color)
            painter.drawText(QRect(x, top, w, height), int(Qt.AlignVCenter | Qt.AlignLeft), s)
            x += w + cw

        level = entry.level
        lvl_color = self._level_text.get(level, self._muted)
        # Fixed column widths; long tag/package values elide in the middle so the
        # ends stay legible (e.g. 'vendor.xia....0-service').
        seg(time_str, _TIME_W, base_fg)
        seg(f"{entry.pid}-{entry.tid}", _PIDTID_W, base_fg)
        seg(entry.tag, _TAG_W, base_fg, elide="middle")
        if self.show_process:
            # Always reserve the column when enabled so the toggle has visible
            # effect; names fill in as `adb ps` / Start proc lines resolve them.
            seg(index.data(PROCESS_ROLE) or "", _PROC_W, base_fg, elide="middle")

        chip = QRect(x, top + 2, 2 * cw, height - 4)
        # Always the level color — filling it with the (white) selection fg on a
        # selected row would put the white chip letter on white and hide it.
        painter.fillRect(chip, lvl_color)
        painter.setPen(self._chip_fg)
        painter.drawText(chip, int(Qt.AlignCenter), level)
        x += 3 * cw

        msg_color = self._sel_fg if selected else lvl_color
        painter.setPen(msg_color)
        mr = QRect(x, top, option.rect.right() - x - self._pad, height)
        painter.drawText(
            mr,
            int(Qt.AlignVCenter | Qt.AlignLeft),
            fm.elidedText(entry.message, Qt.ElideRight, mr.width()),
        )
        painter.restore()
