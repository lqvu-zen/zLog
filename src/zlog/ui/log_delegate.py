"""One-line-per-entry painter for the log view (Android-Studio-style).

Keeps the model virtualized: the view calls this only for visible rows, so a
million-line capture still renders cheaply. Segments are laid out at fixed
monospace offsets (a table-like alignment without a grid), with the message
tinted per level and a small colored level chip.

When ``wrap`` is on, each row grows to fit its full (word-wrapped) message —
``sizeHint`` computes the exact height, and the view sizes rows to content.
"""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRect, QSize, Qt
from PySide6.QtGui import QColor, QFontMetrics, QTextCharFormat, QTextLayout
from PySide6.QtWidgets import QStyle, QStyledItemDelegate

from zlog.core.trace import frame_hint
from zlog.ui.log_model import (
    DUP_COUNT_ROLE,
    FOLD_ROLE,
    HIGHLIGHT_ROLE,
    MATCH_SPANS_ROLE,
    PROCESS_ROLE,
)

_TIME_MIN_W = 8  # Time/PID size to content (model), never below these floors
_PIDTID_MIN_W = 7
_TAG_W = 22  # natural width of the Tag column (flexible; middle-elides)
_PROC_W = 30  # natural width of the Process column (flexible; middle-elides)
_MSG_MIN_FRAC = 0.5  # the message keeps at least this share of the row width


def plan_tag_proc_widths(usable, cw, show, fixed_px, min_frac=_MSG_MIN_FRAC):
    """Return (tag_px, proc_px) for the flexible columns.

    ``fixed_px`` is the footprint already taken by the always-full columns
    (Time + PID + Level, incl. their gaps). Tag and the optional Process column
    share what's left so the message keeps at least ``min_frac`` of ``usable``;
    they use their natural widths when there's room, else shrink proportionally.
    Pure arithmetic (no Qt) so it's unit-testable.
    """
    gap = cw
    nat_tag = _TAG_W * cw
    nat_proc = _PROC_W * cw if show else 0
    gaps = gap * (2 if show else 1)
    budget = max(0.0, usable - fixed_px - min_frac * usable)
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
        self._inline_match = QColor("#8ec4f5")
        self._pad = 6
        self.row_pad = 4  # extra vertical px per row (density preset; see core/density.py)
        self.line_numbers = False  # paint a left gutter of source-row numbers
        self.show_process = False  # paint the process/package column
        self.wrap = False  # wrap long messages across as many lines as needed
        self.collapse = False  # paint a ×N badge on collapsed-duplicate representatives
        self.view = None  # set by MainWindow; used to read the column width in sizeHint

    def set_theme(
        self,
        muted: str,
        meta: str,
        level_text: dict[str, str],
        chip_fg: str,
        selection_bg: str,
        selection_text: str,
        row_hover_bg: str,
        inline_match: str = "#8ec4f5",
    ) -> None:
        self._muted = QColor(muted)
        self._meta = QColor(meta)
        self._level_text = {k: QColor(v) for k, v in level_text.items()}
        self._chip_fg = QColor(chip_fg)
        self._sel_bg = QColor(selection_bg)
        self._sel_fg = QColor(selection_text)
        self._hover_bg = QColor(row_hover_bg)
        self._inline_match = QColor(inline_match)

    def _col_widths(self, left, right, cw, src, fm):
        """Pixel widths of the (content-sized) Time/PID and (flexible) Tag/Process
        columns — shared by paint and sizeHint so their layouts agree."""

        def cols(getter, floor):
            fn = getattr(src, getter, None)
            return max(fn() if fn else 0, floor)

        # Measure the actual glyph run (not char_count * M-width): per-character
        # advance rounding otherwise makes the box a few px too narrow and clips the
        # last digit of the timestamp. Both stamps are digits/punctuation, so a run of
        # "0"s gives the true — and, for non-monospace fallbacks, safely padded — width.
        time_w = fm.horizontalAdvance("0" * cols("time_col_chars", _TIME_MIN_W))
        pid_w = fm.horizontalAdvance("0" * cols("pidtid_col_chars", _PIDTID_MIN_W))
        fixed_px = (time_w + cw) + (pid_w + cw) + 3 * cw
        x0 = left + self._pad
        usable = (right - self._pad) - x0
        tag_w, proc_w = plan_tag_proc_widths(usable, cw, self.show_process, fixed_px)
        return time_w, pid_w, tag_w, proc_w

    def _gutter_w(self, src, fm):
        """Pixel width of the line-number gutter (0 when off). Sized to the digit
        count of the source model's row count, so numbers right-align in a stable
        column across a viewport of appends. Kept in sync between paint and sizeHint."""
        if not self.line_numbers or src is None:
            return 0
        fn = getattr(src, "rowCount", None)
        rows = max(1, fn() if fn else 1)
        digits = len(str(rows))
        return fm.horizontalAdvance("0" * digits) + 2 * self._pad

    def _msg_left(self, left, time_w, pid_w, tag_w, proc_w, cw):
        """The x where the message starts (after Time/PID/Tag/[Process]/level chip)."""
        x = left + self._pad + (time_w + cw) + (pid_w + cw) + (tag_w + cw)
        if self.show_process:
            x += proc_w + cw
        return x + 3 * cw

    def sizeHint(self, option, index):
        fm = QFontMetrics(option.font)
        line_h = fm.height()
        if not self.wrap or index is None or not index.isValid():
            return QSize(0, line_h + self.row_pad)
        entry = index.data(Qt.UserRole)
        message = entry.message if entry is not None else (index.data(Qt.DisplayRole) or "")
        # sizeHintForRow doesn't give the column width in option.rect, so read it
        # from the view (a single stretched column == the viewport width).
        width = option.rect.width()
        if width <= 0 and self.view is not None:
            width = self.view.viewport().width()
        width = width if width > 0 else 800
        cw = fm.horizontalAdvance("M") or 8
        src = index.model()
        src = src.sourceModel() if hasattr(src, "sourceModel") else src
        gutter = self._gutter_w(src, fm)  # the message column starts after the gutter
        if entry is None or not entry.level:
            avail = width - 2 * self._pad - gutter
        else:
            time_w, pid_w, tag_w, proc_w = self._col_widths(gutter, width, cw, src, fm)
            avail = (width - self._pad) - self._msg_left(gutter, time_w, pid_w, tag_w, proc_w, cw)
        avail = max(int(avail), cw * 4)
        rect = fm.boundingRect(0, 0, avail, 1_000_000, int(Qt.TextWordWrap), message)
        return QSize(0, max(line_h, rect.height()) + self.row_pad)

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
        painter.setFont(option.font)
        # In wrap mode metadata sits on the first line (band); the message wraps
        # into the full row height. Otherwise everything is one vertically-centered line.
        band = (fm.height() + self.row_pad) if self.wrap else height

        src = index.model()
        src = src.sourceModel() if hasattr(src, "sourceModel") else src
        # Optional line-number gutter: shifts every column right by its width and
        # paints the row's absolute (source-model) number, right-aligned.
        gutter = self._gutter_w(src, fm)
        left = option.rect.left() + gutter
        x = left + self._pad
        if gutter:
            self._paint_gutter(painter, option, index, fm, gutter, band, selected)

        deco = index.data(Qt.DecorationRole)
        if isinstance(deco, QColor):
            painter.fillRect(QRect(option.rect.left(), top + 2, 3, height - 4), deco)

        base_fg = self._sel_fg if selected else self._meta
        time_str = index.data(Qt.DisplayRole) or ""  # honors the Time display mode
        entry = index.data(Qt.UserRole)

        if entry is None or not entry.level:
            painter.setPen(base_fg)
            text = time_str if entry is None else entry.message
            if self.wrap:
                flags = Qt.AlignTop | Qt.AlignLeft | Qt.TextWordWrap
            else:
                flags = Qt.AlignVCenter | Qt.AlignLeft
            painter.drawText(
                QRect(x, top, option.rect.right() - x - self._pad, height), int(flags), text
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
                painter.drawText(QRect(x, top, w, band), int(Qt.AlignVCenter | Qt.AlignLeft), s)
            x += w + cw

        level = entry.level
        lvl_color = self._level_text.get(level, self._muted)
        show = self.show_process
        time_w, pid_w, tag_w, proc_w = self._col_widths(left, option.rect.right(), cw, src, fm)
        seg(time_str, time_w, base_fg)
        seg(f"{entry.pid}-{entry.tid}", pid_w, base_fg)
        seg(entry.tag, tag_w, base_fg, elide="middle")
        if show:
            seg(index.data(PROCESS_ROLE) or "", proc_w, base_fg, elide="middle")

        chip = QRect(x, top + 2, 2 * cw, band - 4)
        # Always the level color — filling it with the (white) selection fg on a
        # selected row would put the white chip letter on white and hide it.
        painter.fillRect(chip, lvl_color)
        painter.setPen(self._chip_fg)
        painter.drawText(chip, int(Qt.AlignCenter), level)
        x += 3 * cw

        # ×N badge for a run of collapsed duplicates (only when collapse is on).
        if self.collapse:
            count = index.data(DUP_COUNT_ROLE)
            if isinstance(count, int) and count > 1:
                label = f"×{count}"
                badge_w = fm.horizontalAdvance(label) + cw
                badge = QRect(x, top + 2, badge_w, band - 4)
                painter.setPen(self._muted)
                painter.drawRect(badge)
                painter.drawText(badge, int(Qt.AlignCenter), label)
                x += badge_w + cw

        # Stack-trace disclosure: a ▶/▼ glyph on a header row that has frames,
        # with a "… N frames" hint appended when folded.
        fold = index.data(FOLD_ROLE)
        message = entry.message
        if fold:
            _has, folded, count = fold
            painter.setPen(base_fg)
            glyph = "▶" if folded else "▼"
            gw = fm.horizontalAdvance("▶") + cw // 2
            painter.drawText(QRect(x, top, gw, band), int(Qt.AlignVCenter | Qt.AlignLeft), glyph)
            x += gw
            if folded:
                message = f"{message}  {frame_hint(count)}"

        msg_color = self._sel_fg if selected else lvl_color
        painter.setPen(msg_color)
        mr = QRect(x, top, option.rect.right() - x - self._pad, height)
        spans = index.data(MATCH_SPANS_ROLE)
        if spans:
            self._draw_message_with_spans(painter, mr, message, spans, option.font, msg_color)
        elif self.wrap:
            painter.drawText(mr, int(Qt.AlignTop | Qt.AlignLeft | Qt.TextWordWrap), message)
        else:
            painter.drawText(
                mr,
                int(Qt.AlignVCenter | Qt.AlignLeft),
                fm.elidedText(message, Qt.ElideRight, mr.width()),
            )
        painter.restore()

    def _paint_gutter(self, painter, option, index, fm, gutter, band, selected) -> None:
        """Paint the row's absolute (source-model) line number, right-aligned in
        the left gutter, plus a hair-line divider. Uses the source row so the
        number is stable across filtering (matching bookmark/incident indexing)."""
        model = index.model()
        src_row = model.mapToSource(index).row() if hasattr(model, "mapToSource") else index.row()
        left, top = option.rect.left(), option.rect.top()
        # Align to the metadata band (the first line in wrap mode), like the columns.
        num_rect = QRect(left, top, gutter - self._pad, band)
        painter.setPen(self._sel_fg if selected else self._muted)
        painter.drawText(num_rect, int(Qt.AlignRight | Qt.AlignVCenter), str(src_row + 1))
        painter.setPen(self._muted)
        gx = left + gutter - self._pad // 2
        painter.drawLine(gx, top, gx, option.rect.bottom())

    def _draw_message_with_spans(self, painter, rect, message, spans, font, color) -> None:
        """Paint `message` in `rect`, tinting `spans` (char offsets) with the
        inline-match color behind the text. Only reached when the row has an
        active highlight match, so this is off the hot path for ordinary rows.

        Uses QTextLayout (not plain drawText) because it's the only Qt
        primitive that lays out word-wrapped text *and* accepts per-character
        background formatting — matching drawText(Qt.TextWordWrap)'s line
        breaks exactly, including across multiple wrapped lines.
        """
        layout = QTextLayout(message, font)
        fmt = QTextCharFormat()
        fmt.setBackground(self._inline_match)
        ranges = []
        for start, end in spans:
            r = QTextLayout.FormatRange()
            r.start, r.length, r.format = start, end - start, fmt
            ranges.append(r)
        layout.setFormats(ranges)
        layout.beginLayout()
        line_width = rect.width() if self.wrap else 10_000_000  # unbounded: one line
        y = 0.0
        first_line = None
        while True:
            line = layout.createLine()
            if not line.isValid():
                break
            line.setLineWidth(line_width)
            line.setPosition(QPointF(0, y))
            y += line.height()
            first_line = first_line or line
            if not self.wrap:
                break
        layout.endLayout()
        painter.save()
        painter.setPen(color)
        top = rect.top()
        if not self.wrap:
            # Single line, vertically centered like the plain drawText path;
            # clipped since an overlong match isn't elided here (rare: only
            # matched + longer-than-the-cell rows lose the "…" affordance).
            painter.setClipRect(rect)
            line_h = first_line.height() if first_line else 0
            top = rect.top() + (rect.height() - line_h) / 2
        layout.draw(painter, QPointF(rect.left(), top))
        painter.restore()
