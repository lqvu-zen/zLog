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
from contextlib import contextmanager

from PySide6.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    QSortFilterProxyModel,
    Qt,
    Signal,
)
from PySide6.QtGui import QColor

from zlog.core.incidents import classify_incident
from zlog.core.models import LEVEL_RANK, LogEntry
from zlog.core.plugins import apply_colorizers
from zlog.core.proc import parse_proc_start
from zlog.core.search import compile_matcher, find_spans
from zlog.core.timefmt import format_delta, in_time_range, parse_logcat_time
from zlog.core.trace import is_stack_frame
from zlog.ui.theme import LIGHT

COLUMNS = ["Time", "PID", "TID", "Level", "Tag", "Message"]
MESSAGE_COL = 5
HIGHLIGHT_ROLE = int(Qt.UserRole) + 1  # tag/search highlight only (no level tint)
PROCESS_ROLE = int(Qt.UserRole) + 2  # resolved process/package name for the row's PID
MATCH_SPANS_ROLE = int(Qt.UserRole) + 3  # (start, end) spans of the highlight match in message
DUP_COUNT_ROLE = int(Qt.UserRole) + 4  # run length of a collapsed-duplicate representative row
FOLD_ROLE = int(Qt.UserRole) + 5  # (has_frames, is_folded, frame_count) for a stack-trace header
_TIME_MAX_CHARS = 24  # cap the (content-sized) Time column; full stamp fits in 23
_PIDTID_MAX_CHARS = 13


class LogTableModel(QAbstractTableModel):
    bookmarksChanged = Signal()  # bookmarks added/removed/labeled (for the Bookmarks dock)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._rows: list[LogEntry] = []
        self._level_colors: dict[str, QColor] = {}
        self._tag_colors: dict[str, QColor] = {}  # per-tag highlight, overrides level tint
        self._highlight_rules: list = []  # compiled (matcher, pattern, regex, QColor) rules
        self._level_counts: Counter = Counter()
        self._highlight = None  # optional match predicate for highlight mode
        self._highlight_spans_fn = None  # message -> [(start, end), ...] for the same term
        self._highlight_color = QColor(LIGHT.search_highlight)
        self._time_mode = "absolute"  # "absolute" | "since_start" | "delta"
        self._baseline = None  # datetime of the first parseable row (since_start ref)
        self._bookmarks: dict[int, str] = {}  # source-row index -> label ("" = unlabeled)
        self._bookmark_color = QColor(LIGHT.bookmark)
        self._incidents: dict[int, str] = {}  # source row -> "crash" | "anr"
        self._run_len: list[int] = []  # per-row consecutive-duplicate run length (0 on non-reps)
        self._run_rep = -1  # source index of the current run's representative row
        self._frame_header: list[int] = []  # per-row header index for a stack frame, else -1
        self._header_frames: dict[int, int] = {}  # header source row -> frame count
        self._folded: set[int] = set()  # header rows whose frames are currently hidden
        self._max_rows = 0  # ring-buffer cap; 0 = unlimited
        self._colorizers = []  # plugin colorize(entry) callables
        self._pid_names: dict[str, str] = {}  # pid -> process/package name
        self._time_col_chars = 0  # Time/PID columns size to content (only grow)
        self._pidtid_col_chars = 0
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
            rule_color = self._rule_color(entry)
            if rule_color is not None:
                return rule_color
            if self._colorizers:
                c = apply_colorizers(self._colorizers, entry)
                if c:
                    return QColor(c)
            if self._highlight is not None and self._highlight(f"{entry.tag} {entry.message}"):
                return self._highlight_color
            return self._level_colors.get(entry.level)
        if role == Qt.UserRole:
            return entry
        if role == PROCESS_ROLE:
            return self._pid_names.get(entry.pid, "")
        if role == HIGHLIGHT_ROLE:
            tag = self._tag_colors.get(entry.tag)
            if tag is not None:
                return tag
            rule_color = self._rule_color(entry)
            if rule_color is not None:
                return rule_color
            if self._colorizers:
                c = apply_colorizers(self._colorizers, entry)
                if c:
                    return QColor(c)
            if self._highlight is not None and self._highlight(f"{entry.tag} {entry.message}"):
                return self._highlight_color
            return None
        if role == MATCH_SPANS_ROLE:
            if (
                self._highlight is not None
                and self._highlight_spans_fn is not None
                and self._highlight(f"{entry.tag} {entry.message}")
            ):
                return self._highlight_spans_fn(entry.message)
            return []
        if role == DUP_COUNT_ROLE:
            return self.run_length(index.row())
        if role == FOLD_ROLE:
            count = self._header_frames.get(index.row(), 0)
            if count == 0:
                return None  # not a trace header
            return (True, index.row() in self._folded, count)
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
    @staticmethod
    def _same_as_prev(a: LogEntry, b: LogEntry) -> bool:
        return (a.level, a.tag, a.message) == (b.level, b.tag, b.message)

    def append_entries(self, entries: list[LogEntry]) -> None:
        if not entries:
            return
        first = len(self._rows)
        last = first + len(entries) - 1
        self.beginInsertRows(QModelIndex(), first, last)
        self._rows.extend(entries)
        for offset, entry in enumerate(entries):
            idx = first + offset
            self._level_counts[entry.level] += 1
            kind = classify_incident(entry)
            if kind is not None:
                self._incidents[idx] = kind
            # Consecutive-duplicate run length: a row identical to the one before
            # it extends the current run (the representative carries the count);
            # otherwise it starts a fresh run. Mirrors the collapse gate's rule.
            if idx > 0 and self._same_as_prev(entry, self._rows[idx - 1]):
                self._run_len.append(0)
                self._run_len[self._run_rep] += 1
            else:
                self._run_rep = idx
                self._run_len.append(1)
            # Stack-trace grouping: a frame line inherits the header of the
            # preceding frame, or (if the previous row isn't a frame) takes that
            # previous row as its header. Non-frame lines get -1.
            if is_stack_frame(entry.message) and idx > 0:
                prev_header = self._frame_header[idx - 1]
                header = prev_header if prev_header >= 0 else idx - 1
                self._frame_header.append(header)
                self._header_frames[header] = self._header_frames.get(header, 0) + 1
            else:
                self._frame_header.append(-1)
            if self._baseline is None:
                self._baseline = parse_logcat_time(entry.time)
            if len(entry.time) > self._time_col_chars:
                self._time_col_chars = min(len(entry.time), _TIME_MAX_CHARS)
            ptl = len(entry.pid) + len(entry.tid) + 1
            if ptl > self._pidtid_col_chars:
                self._pidtid_col_chars = min(ptl, _PIDTID_MAX_CHARS)
            hit = parse_proc_start(entry.message)
            if hit is not None:
                pid, name = hit
                self._pid_names[pid] = name
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
            self._bookmarks = {
                i - overflow: label for i, label in self._bookmarks.items() if i >= overflow
            }
        if self._incidents:
            self._incidents = {
                i - overflow: kind for i, kind in self._incidents.items() if i >= overflow
            }
        # Run lengths are index-aligned to _rows, so drop the trimmed front slice.
        # If the trim removed the current run's representative, promote the new
        # front row to a representative (its count restarts — see the boundary
        # limitation in duplicate-count.md).
        del self._run_len[:overflow]
        self._run_rep -= overflow
        if self._run_rep < 0:
            self._run_rep = 0
            if self._run_len:
                self._run_len[0] = max(self._run_len[0], 1)
        # Fold state is transient UI state: clear it on trim to avoid remapping
        # header keys across the boundary (see stack-trace-folding.md). The
        # index-based _frame_header must shift; a frame whose header was itself
        # trimmed becomes header-less (-1). _header_frames is recounted from the
        # corrected mapping so surviving traces keep their disclosure counts.
        del self._frame_header[:overflow]
        self._frame_header = [h - overflow if h >= overflow else -1 for h in self._frame_header]
        self._folded = set()
        self._header_frames = {}
        for h in self._frame_header:
            if h >= 0:
                self._header_frames[h] = self._header_frames.get(h, 0) + 1
        self.endRemoveRows()

    def clear(self) -> None:
        self.beginResetModel()
        self._rows.clear()
        self._level_counts.clear()
        self._baseline = None
        self._bookmarks.clear()
        self._incidents.clear()
        self._run_len.clear()
        self._run_rep = -1
        self._frame_header.clear()
        self._header_frames.clear()
        self._folded.clear()
        self._time_col_chars = 0
        self._pidtid_col_chars = 0
        self.endResetModel()

    def entry_at(self, row: int) -> LogEntry:
        return self._rows[row]

    def run_length(self, source_row: int) -> int:
        """Consecutive-duplicate run length for a run's representative row
        (1 for a unique line; 0 for a hidden duplicate, which is never shown)."""
        return self._run_len[source_row] if 0 <= source_row < len(self._run_len) else 1

    # --- stack-trace folding ----------------------------------------------
    def header_at(self, source_row: int) -> int:
        """The header source row this frame belongs to, or -1 if it's not a frame."""
        if 0 <= source_row < len(self._frame_header):
            return self._frame_header[source_row]
        return -1

    def frame_count(self, header_row: int) -> int:
        """Number of stack frames grouped under this header (0 if not a header)."""
        return self._header_frames.get(header_row, 0)

    def is_folded(self, header_row: int) -> bool:
        return header_row in self._folded

    def is_frame_hidden(self, source_row: int) -> bool:
        """True if `source_row` is a frame whose header is currently folded."""
        return self._frame_header[source_row] in self._folded

    def toggle_fold(self, header_row: int) -> None:
        """Fold/unfold one trace (a header row with frames)."""
        if self.frame_count(header_row) == 0:
            return
        if header_row in self._folded:
            self._folded.discard(header_row)
        else:
            self._folded.add(header_row)
        self.layoutChanged.emit()

    def fold_all(self) -> None:
        self._folded = set(self._header_frames)
        self.layoutChanged.emit()

    def unfold_all(self) -> None:
        if self._folded:
            self._folded = set()
            self.layoutChanged.emit()

    def all_entries(self) -> list[LogEntry]:
        """A copy of the full master list (used by Save Log)."""
        return list(self._rows)

    def merge_process_names(self, mapping) -> None:
        """Merge a pid -> name map (e.g. from an `adb shell ps` snapshot) and
        repaint the process column. Existing names are overwritten by newer ones."""
        changed = False
        for pid, name in dict(mapping).items():
            if name and self._pid_names.get(str(pid)) != str(name):
                self._pid_names[str(pid)] = str(name)
                changed = True
        if changed and self._rows:
            top = self.index(0, 0)
            bottom = self.index(len(self._rows) - 1, len(COLUMNS) - 1)
            self.dataChanged.emit(top, bottom, [PROCESS_ROLE])

    def process_name(self, pid: str) -> str:
        return self._pid_names.get(pid, "")

    def process_names(self) -> list[str]:
        """Sorted, de-duplicated process/package names seen in the log (from
        'Start proc' lines and any merged `adb ps` snapshot). Drives the
        log-driven package selector."""
        return sorted({name for name in self._pid_names.values() if name})

    def clear_process_names(self) -> None:
        """Forget the pid -> name map (used when loading an offline log, whose
        PIDs belong to a different capture than the live device)."""
        if self._pid_names:
            self._pid_names.clear()
            if self._rows:
                top = self.index(0, 0)
                bottom = self.index(len(self._rows) - 1, len(COLUMNS) - 1)
                self.dataChanged.emit(top, bottom, [PROCESS_ROLE])

    def time_col_chars(self) -> int:
        return self._time_col_chars

    def pidtid_col_chars(self) -> int:
        return self._pidtid_col_chars

    def set_level_colors(self, hexmap: dict[str, str]) -> None:
        """Set per-level row tints from a theme's hex values (W/E/F)."""
        self._level_colors = {level: QColor(value) for level, value in hexmap.items()}

    def set_highlight(self, text: str, regex: bool = False, case: bool = False) -> bool:
        """Set the highlight predicate (highlight mode). Empty text clears it.
        Returns False on an invalid regex, keeping the previous predicate."""
        if not text:
            self._highlight = None
            self._highlight_spans_fn = None
            self._repaint_backgrounds()
            return True
        try:
            self._highlight = compile_matcher(text, regex, case)
        except re.error:
            return False
        self._highlight_spans_fn = lambda s: find_spans(s, text, regex, case)
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

    def set_colorizers(self, fns) -> None:
        """Install plugin colorize(entry) callables and repaint."""
        self._colorizers = list(fns)
        self._repaint_backgrounds()

    def tag_colors(self) -> dict[str, str]:
        """Current tag highlights as hex strings (for saving)."""
        return {tag: color.name() for tag, color in self._tag_colors.items()}

    def set_highlight_rules(self, rules: list[dict]) -> None:
        """Install persistent term/regex -> color rules (see core/highlight_rules.py).
        A rule whose pattern fails to compile as regex is skipped, same
        tolerance `set_search`/`set_exclude` already have."""
        compiled = []
        for rule in rules:
            try:
                matcher = compile_matcher(rule["pattern"], rule["regex"])
            except re.error:
                continue
            compiled.append((matcher, rule["pattern"], rule["regex"], QColor(rule["color"])))
        self._highlight_rules = compiled
        self._repaint_backgrounds()

    def highlight_rules(self) -> list[dict]:
        """Current highlight rules as plain dicts (for saving)."""
        return [
            {"pattern": pattern, "regex": regex, "color": color.name()}
            for _matcher, pattern, regex, color in self._highlight_rules
        ]

    def _rule_color(self, entry: LogEntry) -> QColor | None:
        """First highlight rule matching this row's tag+message, or None."""
        if not self._highlight_rules:
            return None
        haystack = f"{entry.tag} {entry.message}"
        for matcher, _pattern, _regex, color in self._highlight_rules:
            if matcher(haystack):
                return color
        return None

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
            del self._bookmarks[source_row]
        else:
            self._bookmarks[source_row] = ""
        top = self.index(source_row, 0)
        self.dataChanged.emit(top, top, [Qt.DecorationRole])
        self.bookmarksChanged.emit()

    def is_bookmarked(self, source_row: int) -> bool:
        return source_row in self._bookmarks

    def bookmarked_rows(self) -> list[int]:
        """Bookmarked source rows, in order."""
        return sorted(self._bookmarks)

    def bookmark_label(self, source_row: int) -> str:
        """The label for a bookmarked row ("" if none / not bookmarked)."""
        return self._bookmarks.get(source_row, "")

    def bookmarks(self) -> dict[int, str]:
        """A copy of the {source-row: label} bookmark map (for session save)."""
        return dict(self._bookmarks)

    def set_bookmark_label(self, source_row: int, text: str) -> None:
        """Attach/replace a bookmark's label. No-op if the row isn't bookmarked."""
        if source_row in self._bookmarks:
            self._bookmarks[source_row] = text or ""
            self.bookmarksChanged.emit()

    def clear_bookmarks(self) -> None:
        self._bookmarks.clear()
        self._repaint_bookmarks()
        self.bookmarksChanged.emit()

    def set_bookmarks(self, rows) -> None:
        """Replace the bookmarks (restoring a session), clamped to valid source
        rows. Accepts a list of rows (unlabeled) or a {row: label} mapping."""
        n = len(self._rows)
        if isinstance(rows, dict):
            self._bookmarks = {int(r): str(v) for r, v in rows.items() if 0 <= int(r) < n}
        else:
            self._bookmarks = {int(r): "" for r in rows if 0 <= int(r) < n}
        self._repaint_bookmarks()
        self.bookmarksChanged.emit()

    def _repaint_bookmarks(self) -> None:
        if self._rows:
            top = self.index(0, 0)
            bottom = self.index(len(self._rows) - 1, 0)
            self.dataChanged.emit(top, bottom, [Qt.DecorationRole])

    def incident_rows(self) -> list[int]:
        """Source rows classified as a crash/ANR, in order."""
        return sorted(self._incidents)

    def incident_counts(self) -> Counter:
        """Count of detected incidents by kind ("crash"/"anr")."""
        return Counter(self._incidents.values())


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
        self._query_pids: set[str] | None = None  # exact PID gate (pid: token)
        self._proc = ""  # process/package-name contains gate (proc: token)
        self._exclude_pids: set[str] | None = None  # exact PID exclude (-pid: token)
        self._exclude_proc = ""  # process/package-name exclude (-proc: token)
        self._since = None  # since: token — datetime.time, inclusive lower bound
        self._until = None  # until: token — datetime.time, inclusive upper bound
        self._batching = False  # see batch_update()

    def _invalidate(self) -> None:
        """Every setter's invalidate hook — routed through here so a
        batch_update() block can defer them all to a single real pass."""
        if not self._batching:
            self.invalidate()

    @contextmanager
    def batch_update(self):
        """Suppress each setter's own invalidate() while multiple run inside
        the block, then invalidate exactly once on exit — turns N full
        re-filter passes (one per setter) into 1. Applying a parsed query bar
        touches ~9 setters per keystroke; without this, each one re-runs
        filterAcceptsRow over the whole buffer."""
        self._batching = True
        try:
            yield
        finally:
            self._batching = False
            self.invalidate()

    def set_min_level(self, level_letter: str) -> None:
        self._min_level = LEVEL_RANK.get(level_letter, 0)
        self._invalidate()

    def set_search(self, text: str, regex: bool, case: bool = False) -> bool:
        """Set the search matcher. Returns False (keeping the previous matcher) if
        `regex` is True and `text` is an invalid pattern, so the caller can flag it."""
        try:
            matcher = compile_matcher(text, regex, case)
        except re.error:
            return False
        self._matcher = matcher
        self._invalidate()
        return True

    def set_exclude(self, text: str, regex: bool = False, case: bool = False) -> bool:
        """Set the exclude matcher — rows it matches are hidden. Empty text clears
        it. Returns False on an invalid regex, keeping the previous matcher."""
        if not text:
            self._exclude = None
            self._invalidate()
            return True
        try:
            self._exclude = compile_matcher(text, regex, case)
        except re.error:
            return False
        self._invalidate()
        return True

    def set_levels(self, levels) -> None:
        """Restrict to an exact set of level letters, or None to use the min-level
        floor instead."""
        self._levels = set(levels) if levels else None
        self._invalidate()

    def set_tag(self, text: str) -> None:
        """Restrict to rows whose tag contains this text (case-insensitive); "" = off."""
        self._tag = text.lower()
        self._invalidate()

    def set_pids(self, pids) -> None:
        """Restrict to these PID strings, or pass None to clear the package filter."""
        self._pids = set(pids) if pids is not None else None
        self._invalidate()

    def set_collapse(self, on: bool) -> None:
        """Hide consecutive duplicate lines (same level/tag/message) when on."""
        self._collapse = bool(on)
        self._invalidate()

    def set_query_pids(self, pids) -> None:
        """Keep only these exact PID strings (pid: token), or None to clear."""
        self._query_pids = set(pids) if pids else None
        self._invalidate()

    def set_proc(self, text: str) -> None:
        """Keep rows whose resolved process/package name contains this text."""
        self._proc = text.lower()
        self._invalidate()

    def set_exclude_pids(self, pids) -> None:
        """Hide these exact PID strings (-pid: token), or None to clear."""
        self._exclude_pids = set(pids) if pids else None
        self._invalidate()

    def set_exclude_proc(self, text: str) -> None:
        """Hide rows whose resolved process/package name contains this text
        (-proc: token); "" = off."""
        self._exclude_proc = text.lower()
        self._invalidate()

    def set_time_range(self, since, until) -> None:
        """Restrict to rows whose time-of-day is within [since, until]
        (each a `datetime.time` or None to leave that bound open)."""
        self._since = since
        self._until = until
        self._invalidate()

    def level_counts(self) -> dict[str, int]:
        """Count of currently-accepted rows per level letter (walks filtered rows,
        unlike LogTableModel.level_counts which is O(1) over the whole buffer)."""
        model: LogTableModel = self.sourceModel()
        counts: Counter = Counter()
        for r in range(self.rowCount()):
            source_row = self.mapToSource(self.index(r, 0)).row()
            counts[model.entry_at(source_row).level] += 1
        return dict(counts)

    def filterAcceptsRow(self, source_row, source_parent) -> bool:
        model: LogTableModel = self.sourceModel()
        entry = model.entry_at(source_row)
        # Stack-trace folding: hide a frame line whose header is folded (a no-op
        # when nothing is folded, since is_frame_hidden is then always False).
        if model.is_frame_hidden(source_row):
            return False
        # Collapse: drop a line identical to the one right before it (device spam).
        if self._collapse and source_row > 0:
            prev = model.entry_at(source_row - 1)
            if (entry.level, entry.tag, entry.message) == (prev.level, prev.tag, prev.message):
                return False
        # Package gate: when active, only rows from those PIDs pass (this hides
        # unparsed/banner lines, whose pid is "").
        if self._pids is not None and entry.pid not in self._pids:
            return False
        # Quick-filter PID gate (pid: token) — exact match on this line's PID.
        if self._query_pids is not None and entry.pid not in self._query_pids:
            return False
        # Quick-filter process gate (proc: token) — the row's resolved
        # process/package name must contain the text.
        if self._proc and self._proc not in model.process_name(entry.pid).lower():
            return False
        # Negative PID/process gates (-pid:/-proc: tokens) — hide matching rows.
        if self._exclude_pids is not None and entry.pid in self._exclude_pids:
            return False
        if self._exclude_proc and self._exclude_proc in model.process_name(entry.pid).lower():
            return False
        # Time-range gate (since:/until: tokens) — an unparseable timestamp
        # always passes, same rule the level gate applies to unparsed lines.
        if (self._since is not None or self._until is not None) and not in_time_range(
            entry.time, self._since, self._until
        ):
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
