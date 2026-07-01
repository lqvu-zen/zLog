"""Qt table model + filter proxy.

LogTableModel holds every entry but is *virtualized*: QTableView only asks for
the rows currently on screen, so a million lines cost almost nothing to render.

LogFilterProxy sits between model and view and decides which rows show, based on
a minimum level, a search matcher (substring or regex), and (optionally) a set of
PIDs for a chosen package. Filtering this way keeps the master list intact, so
clearing a filter instantly restores everything.

Row tint colors come from the active theme (see `ui/theme.py`), applied per
instance via `LogTableModel.set_level_colors` so a theme switch repaints live.
"""

from __future__ import annotations

import re

from PySide6.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    QSortFilterProxyModel,
    Qt,
)
from PySide6.QtGui import QColor

from zlog.core.models import LEVEL_RANK, LogEntry
from zlog.core.search import compile_matcher
from zlog.ui.theme import LIGHT

COLUMNS = ["Time", "PID", "TID", "Level", "Tag", "Message"]
MESSAGE_COL = 5


class LogTableModel(QAbstractTableModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._rows: list[LogEntry] = []
        self._level_colors: dict[str, QColor] = {}
        self.set_level_colors(LIGHT.level_colors)

    # --- required overrides ------------------------------------------------
    def rowCount(self, parent=QModelIndex()) -> int:
        return len(self._rows)

    def columnCount(self, parent=QModelIndex()) -> int:
        return len(COLUMNS)

    def data(self, index: QModelIndex, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        entry = self._rows[index.row()]
        if role == Qt.DisplayRole:
            return (
                entry.time,
                entry.pid,
                entry.tid,
                entry.level,
                entry.tag,
                entry.message,
            )[index.column()]
        if role == Qt.BackgroundRole:
            return self._level_colors.get(entry.level)
        return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return COLUMNS[section]
        return None

    # --- helpers -----------------------------------------------------------
    def append_entries(self, entries: list[LogEntry]) -> None:
        if not entries:
            return
        first = len(self._rows)
        last = first + len(entries) - 1
        self.beginInsertRows(QModelIndex(), first, last)
        self._rows.extend(entries)
        self.endInsertRows()

    def clear(self) -> None:
        self.beginResetModel()
        self._rows.clear()
        self.endResetModel()

    def entry_at(self, row: int) -> LogEntry:
        return self._rows[row]

    def all_entries(self) -> list[LogEntry]:
        """A copy of the full master list (used by Save Log)."""
        return list(self._rows)

    def set_level_colors(self, hexmap: dict[str, str]) -> None:
        """Set per-level row tints from a theme's hex values (W/E/F)."""
        self._level_colors = {level: QColor(value) for level, value in hexmap.items()}


class LogFilterProxy(QSortFilterProxyModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._min_level = 0
        self._matcher = compile_matcher("", regex=False)  # match-all by default
        self._pids: set[str] | None = None  # None = no package filter

    def set_min_level(self, level_letter: str) -> None:
        self._min_level = LEVEL_RANK.get(level_letter, 0)
        self.invalidateFilter()

    def set_search(self, text: str, regex: bool) -> bool:
        """Set the search matcher. Returns False (keeping the previous matcher) if
        `regex` is True and `text` is an invalid pattern, so the caller can flag it."""
        try:
            matcher = compile_matcher(text, regex)
        except re.error:
            return False
        self._matcher = matcher
        self.invalidateFilter()
        return True

    def set_pids(self, pids) -> None:
        """Restrict to these PID strings, or pass None to clear the package filter."""
        self._pids = set(pids) if pids is not None else None
        self.invalidateFilter()

    def filterAcceptsRow(self, source_row, source_parent) -> bool:
        model: LogTableModel = self.sourceModel()
        entry = model.entry_at(source_row)
        # Package gate: when active, only rows from those PIDs pass (this hides
        # unparsed/banner lines, whose pid is "").
        if self._pids is not None and entry.pid not in self._pids:
            return False
        # Level gate (unparsed lines, level "", always pass).
        if entry.level and entry.rank < self._min_level:
            return False
        # Search gate (matcher is match-all when the box is empty).
        return self._matcher(f"{entry.tag} {entry.message}")
