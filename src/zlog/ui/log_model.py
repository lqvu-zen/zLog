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
from collections import Counter

from PySide6.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    QSortFilterProxyModel,
    Qt,
)
from PySide6.QtGui import QColor

from zlog.core.models import LEVEL_RANK, LogEntry
from zlog.core.search import compile_matcher
from zlog.core.timefmt import format_delta, parse_logcat_time
from zlog.ui.theme import LIGHT

COLUMNS = ["Time", "PID", "TID", "Level", "Tag", "Message"]
MESSAGE_COL = 5
HIGHLIGHT_ROLE = int(Qt.UserRole) + 1  # tag/search highlight only (no level tint)


class LogTableModel(QAbstractTableModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._rows: list[LogEntry] = []
        self._level_colors: dict[str, QColor] = {}
        self._tag_colors: dict[str, QColor] = {}  # per-tag highlight, overrides level tint
        self._level_counts: Counter = Counter()
        self._highlight = None  # optional match predicate for highlight mode
        self._highlight_color = QColor(LIGHT.search_highlight)
        self._time_mode = "absolute"  # "absolute" | "since_start" | "delta"
        self._baseline = None  # datetime of the first parseable row (since_start ref)
        self._bookmarks: set[int] = set()  # bookmarked source-row indices
        self._bookmark_color = QColor(LIGHT.bookmark)
        self._max_rows = 0  # ring-buffer cap; 0 = unlimited
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
            if index.column() == 0 and self._time_mode != "absolute":
                return self._relative_time(index.row())
            return (
                entry.time,
                entry.pid,
                entry.tid,
                entry.level,
                entry.tag,
                entry.message,
            )[index.column()]
        if role == Qt.BackgroundRole:
            tag = self._tag_colors.get(entry.tag)
            if tag is not None:
                return tag
            if self._highlight is not None and self._highlight(f"{entry.tag} {entry.message}"):
                return self._highlight_color
            return self._level_colors.get(entry.level)
        if role == Qt.UserRole:
            return entry
        if role == HIGHLIGHT_ROLE:
            tag = self._tag_colors.get(entry.tag)
            if tag is not None:
                return tag
            if self._highlight is not None and self._highlight(f"{entry.tag} {entry.message}"):
                return self._highlight_color
            return None
        if role == Qt.DecorationRole and index.column() == 0:
            return self._bookmark_color if index.row() in self._bookmarks else None
        if role == Qt.TextAlignmentRole and index.column() in (1, 2):
            return int(Qt.AlignRight | Qt.AlignVCenter)
        return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal:
            if role == Qt.DisplayRole:
                return COLUMNS[section]
            if role == Qt.TextAlignmentRole:
                # Mirror each column's cell alignment so the header sits over its
                # data instead of Qt's default center (most visible on the wide,
                # left-aligned, stretched Message column).
                if section in (1, 2):
                    return int(Qt.AlignRight | Qt.AlignVCenter)
                return int(Qt.AlignLeft | Qt.AlignVCenter)
        return None

    # --- helpers -----------------------------------------------------------
    def append_entries(self, entries: list[LogEntry]) -> None:
        if not entries:
            return
        first = len(self._rows)
        last = first + len(entries) - 1
        self.beginInsertRows(QModelIndex(), first, last)
        self._rows.extend(entries)
        for entry in entries:
            self._level_counts[entry.level] += 1
            if self._baseline is None:
                self._baseline = parse_logcat_time(entry.time)
        self.endInsertRows()
        self._enforce_cap()

    def set_max_rows(self, n: int) -> None:
        """Cap the master list to the last `n` entries (0 = unlimited). Applying a
        tighter cap trims immediately; a looser/zero one just changes future appends."""
        self._max_rows = max(0, int(n))
        self._enforce_cap()

    def _enforce_cap(self) -> None:
        """Drop the oldest rows past the cap, keeping counts/bookmarks consistent.

        Uses beginRemoveRows (not a reset) so the view stays virtualized. Bookmarks
        are source-row indices, so they shift down by the number dropped; any that
        referred to a trimmed row are discarded.
        """
        if self._max_rows <= 0:
            return
        overflow = len(self._rows) - self._max_rows
        if overflow <= 0:
            return
        self.beginRemoveRows(QModelIndex(), 0, overflow - 1)
        dropped = self._rows[:overflow]
        del self._rows[:overflow]
        for entry in dropped:
            self._level_counts[entry.level] -= 1
            if self._level_counts[entry.level] <= 0:
                del self._level_counts[entry.level]
        if self._bookmarks:
            self._bookmarks = {i - overflow for i in self._bookmarks if i >= overflow}
        self.endRemoveRows()

    def clear(self) -> None:
        self.beginResetModel()
        self._rows.clear()
        self._level_counts.clear()
        self._baseline = None
        self._bookmarks.clear()
        self.endResetModel()

    def entry_at(self, row: int) -> LogEntry:
        return self._rows[row]

    def all_entries(self) -> list[LogEntry]:
        """A copy of the full master list (used by Save Log)."""
        return list(self._rows)

    def set_level_colors(self, hexmap: dict[str, str]) -> None:
        """Set per-level row tints from a theme's hex values (W/E/F)."""
        self._level_colors = {level: QColor(value) for level, value in hexmap.items()}

    def set_highlight(self, text: str, regex: bool = False, case: bool = False) -> bool:
        """Set the highlight predicate (highlight mode). Empty text clears it.
        Returns False on an invalid regex, keeping the previous predicate."""
        if not text:
            self._highlight = None
            self._repaint_backgrounds()
            return True
        try:
            self._highlight = compile_matcher(text, regex, case)
        except re.error:
            return False
        self._repaint_backgrounds()
        return True

    def set_highlight_color(self, color: str) -> None:
        """Set the highlight tint (from the active theme's `search_highlight`)."""
        self._highlight_color = QColor(color)
        self._repaint_backgrounds()

    def _repaint_backgrounds(self) -> None:
        """Ask the view to re-query BackgroundRole for the current rows."""
        if self._rows:
            top = self.index(0, 0)
            bottom = self.index(len(self._rows) - 1, len(COLUMNS) - 1)
            self.dataChanged.emit(top, bottom, [Qt.BackgroundRole])

    def set_tag_color(self, tag: str, color: str) -> None:
        """Highlight all rows with this tag using the given color (hex or name)."""
        if tag:
            self._tag_colors[tag] = QColor(color)

    def clear_tag_colors(self) -> None:
        self._tag_colors = {}

    def tag_colors(self) -> dict[str, str]:
        """Current tag highlights as hex strings (for saving)."""
        return {tag: color.name() for tag, color in self._tag_colors.items()}

    def level_counts(self) -> dict[str, int]:
        """Count of rows per level letter across the master list."""
        return dict(self._level_counts)

    def set_time_mode(self, mode: str) -> None:
        """Choose how the Time column reads: absolute stamp, elapsed since the
        first line, or delta from the previous captured line."""
        self._time_mode = mode if mode in ("absolute", "since_start", "delta") else "absolute"
        if self._rows:
            top = self.index(0, 0)
            bottom = self.index(len(self._rows) - 1, 0)
            self.dataChanged.emit(top, bottom, [Qt.DisplayRole])

    def _relative_time(self, row: int) -> str:
        """Time cell for the non-absolute modes; falls back to the raw stamp for
        unparseable (banner) lines."""
        entry = self._rows[row]
        t = parse_logcat_time(entry.time)
        if t is None:
            return entry.time
        if self._time_mode == "delta":
            if row == 0:
                return format_delta(t - t)
            prev = parse_logcat_time(self._rows[row - 1].time)
            return format_delta(t - prev) if prev is not None else entry.time
        # since_start
        if self._baseline is None:
            return entry.time
        return format_delta(t - self._baseline)

    # --- bookmarks ---------------------------------------------------------
    def set_bookmark_color(self, color: str) -> None:
        """Set the bookmark marker color (from the active theme)."""
        self._bookmark_color = QColor(color)
        self._repaint_bookmarks()

    def toggle_bookmark(self, source_row: int) -> None:
        if source_row in self._bookmarks:
            self._bookmarks.discard(source_row)
        else:
            self._bookmarks.add(source_row)
        top = self.index(source_row, 0)
        self.dataChanged.emit(top, top, [Qt.DecorationRole])

    def is_bookmarked(self, source_row: int) -> bool:
        return source_row in self._bookmarks

    def bookmarked_rows(self) -> list[int]:
        """Bookmarked source rows, in order."""
        return sorted(self._bookmarks)

    def clear_bookmarks(self) -> None:
        self._bookmarks.clear()
        self._repaint_bookmarks()

    def set_bookmarks(self, rows) -> None:
        """Replace the bookmark set (used when restoring a session), clamped to
        valid source rows so a stale index can't point out of range."""
        n = len(self._rows)
        self._bookmarks = {int(r) for r in rows if 0 <= int(r) < n}
        self._repaint_bookmarks()

    def _repaint_bookmarks(self) -> None:
        if self._rows:
            top = self.index(0, 0)
            bottom = self.index(len(self._rows) - 1, 0)
            self.dataChanged.emit(top, bottom, [Qt.DecorationRole])


class LogFilterProxy(QSortFilterProxyModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._min_level = 0
        self._matcher = compile_matcher("", regex=False)  # match-all by default
        self._exclude = None  # optional predicate; matching rows are hidden
        self._pids: set[str] | None = None  # None = no package filter
        self._tag = ""  # tag-contains gate ("" = off)
        self._levels: set[str] | None = None  # exact level set (None = use min-level floor)
        self._collapse = False  # hide consecutive duplicate lines

    def set_min_level(self, level_letter: str) -> None:
        self._min_level = LEVEL_RANK.get(level_letter, 0)
        self.invalidate()

    def set_search(self, text: str, regex: bool, case: bool = False) -> bool:
        """Set the search matcher. Returns False (keeping the previous matcher) if
        `regex` is True and `text` is an invalid pattern, so the caller can flag it."""
        try:
            matcher = compile_matcher(text, regex, case)
        except re.error:
            return False
        self._matcher = matcher
        self.invalidate()
        return True

    def set_exclude(self, text: str, regex: bool = False, case: bool = False) -> bool:
        """Set the exclude matcher — rows it matches are hidden. Empty text clears
        it. Returns False on an invalid regex, keeping the previous matcher."""
        if not text:
            self._exclude = None
            self.invalidate()
            return True
        try:
            self._exclude = compile_matcher(text, regex, case)
        except re.error:
            return False
        self.invalidate()
        return True

    def set_levels(self, levels) -> None:
        """Restrict to an exact set of level letters, or None to use the min-level
        floor instead."""
        self._levels = set(levels) if levels else None
        self.invalidate()

    def set_tag(self, text: str) -> None:
        """Restrict to rows whose tag contains this text (case-insensitive); "" = off."""
        self._tag = text.lower()
        self.invalidate()

    def set_pids(self, pids) -> None:
        """Restrict to these PID strings, or pass None to clear the package filter."""
        self._pids = set(pids) if pids is not None else None
        self.invalidate()

    def set_collapse(self, on: bool) -> None:
        """Hide consecutive duplicate lines (same level/tag/message) when on."""
        self._collapse = bool(on)
        self.invalidate()

    def filterAcceptsRow(self, source_row, source_parent) -> bool:
        model: LogTableModel = self.sourceModel()
        entry = model.entry_at(source_row)
        # Collapse: drop a line identical to the one right before it (device spam).
        if self._collapse and source_row > 0:
            prev = model.entry_at(source_row - 1)
            if (entry.level, entry.tag, entry.message) == (prev.level, prev.tag, prev.message):
                return False
        # Package gate: when active, only rows from those PIDs pass (this hides
        # unparsed/banner lines, whose pid is "").
        if self._pids is not None and entry.pid not in self._pids:
            return False
        # Level gate: an exact set if one is active, else the min-level floor
        # (unparsed lines, level "", always pass either way).
        if entry.level:
            if self._levels is not None:
                if entry.level not in self._levels:
                    return False
            elif entry.rank < self._min_level:
                return False
        haystack = f"{entry.tag} {entry.message}"
        # Tag gate: when set, the entry's tag must contain it.
        if self._tag and self._tag not in entry.tag.lower():
            return False
        # Exclude gate: hide rows matching the exclude term (if any).
        if self._exclude is not None and self._exclude(haystack):
            return False
        # Search gate (matcher is match-all when the box is empty).
        return self._matcher(haystack)
