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
from PySide6.QtWidgets import QCompleter, QLineEdit, QStyle, QStyleOptionFrame

from zlog.core.completion import completions
from zlog.core.query import token_spans
from zlog.ui.completion_popup import SuggestionDelegate, build_model

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

        # Context-aware autocomplete. The completer is managed manually (setWidget,
        # not setCompleter) so we replace only the *current token* on accept, not the
        # whole line. The suggestion set comes from core.completion + live values the
        # window supplies via set_context_provider.
        self._context_provider = None  # () -> (tags, procs, pids)
        self._comp_span = (0, 0)  # (start, end) of the token being completed
        self._suggest_delegate = SuggestionDelegate()
        self._completer = QCompleter(self)
        self._completer.setWidget(self)
        self._completer.setCompletionMode(QCompleter.UnfilteredPopupCompletion)
        self._completer.setCaseSensitivity(Qt.CaseInsensitive)
        self._completer.popup().setItemDelegate(self._suggest_delegate)
        self._completer.activated[str].connect(self._insert_completion)
        self.textEdited.connect(self._update_completions)

    def set_context_provider(self, fn) -> None:
        """`fn() -> (tags, procs, pids)` supplies live values for tag:/pid:/proc:."""
        self._context_provider = fn

    def set_muted_color(self, color: str) -> None:
        self._suggest_delegate.set_muted(color)

    def _update_completions(self, text: str) -> None:
        """Rebuild the popup for the current token as the user types."""
        tags, procs, pids = ((), (), ())
        if self._context_provider is not None:
            tags, procs, pids = self._context_provider()
        start, end, sugg = completions(text, self.cursorPosition(), tags, procs, pids)
        self._comp_span = (start, end)
        if not sugg:
            self._completer.popup().hide()
            return
        self._completer.setModel(build_model(sugg))
        self._completer.setCompletionPrefix("")  # we already filtered in core
        rect = self.cursorRect()
        rect.setWidth(max(260, self._completer.popup().sizeHintForColumn(0) + 40))
        self._completer.complete(rect)

    def _insert_completion(self, value: str) -> None:
        """Replace the current token span with the chosen value + a trailing space."""
        start, end = self._comp_span
        text = self.text()
        new = text[:start] + value + text[end:]
        caret = start + len(value)
        if caret >= len(new) or new[caret] != " ":
            new = new[:caret] + " " + new[caret:]
        caret += 1
        self.setText(new)  # fires textChanged -> the filter re-applies
        self.setCursorPosition(caret)
        self._completer.popup().hide()

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
