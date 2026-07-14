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
_MSG_MIN_FRAC = 0.5  # the message keeps at least this share of the row width


def plan_tag_proc_widths(usable, cw, show, min_frac=_MSG_MIN_FRAC):
    """Return (tag_px, proc_px) for the flexible columns.

    Time/PID/Level are fixed and always full; Tag and the optional Process column
    share what's left so the message keeps at least ``min_frac`` of ``usable``.
    They use their natural widths when there's room, else shrink proportionally.
    Pure arithmetic (no Qt) so it's unit-testable.
    """
    gap = cw
    time_w, pid_w, level_w = _TIME_W * cw, _PIDTID_W * cw, 3 * cw
    nat_tag = _TAG_W * cw
    nat_proc = _PROC_W * cw if show else 0
    gaps = gap * (2 if show else 1)
    fixed_fp = (time_w + gap) + (pid_w + gap) + level_w
    budget = max(0.0, usable - fixed_fp - min_frac * usable)
    if nat_tag + nat_proc + gaps > budget and nat_tag + nat_proc > 0:
        scale = max(0.0, budget - gaps) / (nat_tag + nat_proc)
        return nat_tag * scale, nat_proc * scale
    return float(nat_tag), float(nat_proc)


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

        def seg(text, width_px, color, elide=None):
            nonlocal x
            w = int(max(width_px, 0))
            s = text or ""
            if elide and w:
                mode = Qt.ElideMiddle if elide == "middle" else Qt.ElideRight
                s = fm.elidedText(s, mode, w)
            if w:
                painter.setPen(color)
                painter.drawText(QRect(x, top, w, height), int(Qt.AlignVCenter | Qt.AlignLeft), s)
            x += w + cw

        level = entry.level
        lvl_color = self._level_text.get(level, self._muted)
        # Time / PID / Level are fixed and always shown in full. Tag and the
        # (optional) process column share a budget sized so the message keeps at
        # least _MSG_MIN_FRAC of the row; when there's room they use their natural
        # widths, otherwise they shrink and middle-elide (ends stay legible).
        usable = (option.rect.right() - self._pad) - x
        show = self.show_process
        tag_w, proc_w = plan_tag_proc_widths(usable, cw, show)
        seg(time_str, _TIME_W * cw, base_fg)
        seg(f"{entry.pid}-{entry.tid}", _PIDTID_W * cw, base_fg)
        seg(entry.tag, tag_w, base_fg, elide="middle")
        if show:
            seg(index.data(PROCESS_ROLE) or "", proc_w, base_fg, elide="middle")

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
