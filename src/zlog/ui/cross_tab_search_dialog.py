"""Search All Tabs dialog — see docs/plans/cross-tab-search.md.

A one-shot, read-only search: it runs the query-bar syntax against every open
tab's full row list via `cross_tab_search.search_sessions` and lists matches
grouped by tab. It never touches any tab's own query/filter state.
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from zlog.core.query import parse_query
from zlog.ui.cross_tab_search import search_sessions, unsupported_gates

# Bounds how many rows the results table ever populates — a query with no gates
# at all (e.g. a blank search) could otherwise match every line of every tab.
# Correctness of the *search* is untouched; only the display is capped.
_MAX_RESULTS = 2000


class CrossTabSearchDialog(QDialog):
    def __init__(
        self, sessions, tab_names: list[str], jump: Callable[[int, int], None], parent=None
    ):
        """`sessions`: the window's session list, in tab order. `tab_names`: a
        display name per session (the caller already knows how to name a tab —
        see `MainWindow._set_tab_label` — so this dialog doesn't reimplement
        that). `jump(session_index, source_row)`: activates that tab and
        selects that row; called on double-click."""
        super().__init__(parent)
        self.setWindowTitle("Search All Tabs")
        self.resize(640, 420)
        self._sessions = sessions
        self._tab_names = tab_names
        self._jump = jump
        self._matches = []

        self.query_edit = QLineEdit()
        self.query_edit.setPlaceholderText("level:E tag:Activity -noise /regex/ …")
        self.query_edit.returnPressed.connect(self._run_search)
        search_btn = QPushButton("Search")
        search_btn.clicked.connect(self._run_search)

        self.hint_label = QLabel("")
        self.hint_label.setWordWrap(True)
        self.hint_label.setStyleSheet("color: gray; font-size: 11px;")

        self.results = QTableWidget(0, 3, self)
        self.results.setHorizontalHeaderLabels(["Tab", "Line", "Entry"])
        self.results.verticalHeader().setVisible(False)
        self.results.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.results.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.results.horizontalHeader().setStretchLastSection(True)
        self.results.cellDoubleClicked.connect(self._activate_row)

        top = QHBoxLayout()
        top.addWidget(self.query_edit)
        top.addWidget(search_btn)

        layout = QVBoxLayout(self)
        layout.addLayout(top)
        layout.addWidget(self.hint_label)
        layout.addWidget(self.results)

        self.query_edit.setFocus()

    def _run_search(self) -> None:
        text = self.query_edit.text()
        spec = parse_query(text)
        self._matches = search_sessions(self._sessions, spec)
        shown = self._matches[:_MAX_RESULTS]

        hints = []
        if unsupported_gates(spec):
            hints.append(
                "proc:/since:/until: aren't supported here and are ignored in this search."
            )
        if len(self._matches) > _MAX_RESULTS:
            hints.append(f"Showing the first {_MAX_RESULTS:,} of {len(self._matches):,} matches.")
        self.hint_label.setText(" ".join(hints))

        self.results.setRowCount(len(shown))
        for i, match in enumerate(shown):
            name = self._tab_names[match.session_index]
            self.results.setItem(i, 0, QTableWidgetItem(name))
            line_item = QTableWidgetItem(str(match.source_row + 1))
            line_item.setTextAlignment(int(Qt.AlignRight | Qt.AlignVCenter))
            self.results.setItem(i, 1, line_item)
            entry = match.entry
            summary = f"{entry.time} {entry.pidtid} {entry.tag} {entry.level} {entry.message}"
            self.results.setItem(i, 2, QTableWidgetItem(summary))
        self.results.resizeColumnToContents(0)
        self.results.resizeColumnToContents(1)

    def _activate_row(self, row: int, _col: int) -> None:
        if not (0 <= row < len(self._matches)):
            return
        match = self._matches[row]
        self._jump(match.session_index, match.source_row)
        self.accept()  # close on jump, matching Tag Summary's double-click behavior
