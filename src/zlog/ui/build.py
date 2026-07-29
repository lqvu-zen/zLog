"""Widget creation and layout for :class:`~zlog.ui.main_window.MainWindow`.

Extracted verbatim from the window so `main_window.py` stays a coordinator rather
than a 3,600-line file (see docs/plans/main-window-split.md). These are plain
functions taking the window and assigning onto it — `win.table`, `win.query`, … —
so every existing `window.<widget>` reference keeps working unchanged.

Call order matters and is owned by `MainWindow.__init__`: widgets, then layout.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDockWidget,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QStatusBar,
    QTabBar,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from zlog.ui.filter_chips import FilterChipBar
from zlog.ui.heat_scrollbar import HeatScrollBar
from zlog.ui.histogram_bar import HistogramBar
from zlog.ui.log_delegate import LogItemDelegate
from zlog.ui.log_model import COLUMNS
from zlog.ui.query_line_edit import QueryLineEdit
from zlog.ui.table_view import LogTableView

# Min-level selector contents. They live here (not in main_window) because the
# level combo is built here and nothing else referenced them.
LEVELS = ["V", "D", "I", "W", "E", "F"]
LEVEL_NAMES = {"V": "Verbose", "D": "Debug", "I": "Info", "W": "Warn", "E": "Error", "F": "Fatal"}


def build_widgets(win) -> None:
    """Create the model/proxy/view and every toolbar widget (no layout yet)."""
    win._sessions = [win._make_session()]
    win._active_index = 0
    win.tab_bar = QTabBar()
    win.tab_bar.setTabsClosable(True)
    win.tab_bar.setMovable(True)  # drag to reorder; _on_tab_moved keeps sessions in sync
    win.tab_bar.setExpanding(False)
    win.tab_bar.setDocumentMode(True)
    win.tab_bar.addTab("Device")
    win._update_tab_closability()
    win.new_tab_btn = QPushButton("+")
    win.new_tab_btn.setObjectName("newTabButton")
    win.new_tab_btn.setToolTip("New tab (Ctrl+T)")
    win.new_tab_btn.setFixedWidth(28)
    win.new_tab_btn.setFocusPolicy(Qt.NoFocus)
    win.new_tab_btn.clicked.connect(win._new_tab)

    win.table = LogTableView()
    win.table.setModel(win.proxy)
    win.heat_bar = HeatScrollBar()  # scrollbar with error-position ticks
    win.table.setVerticalScrollBar(win.heat_bar)
    win.table.setSelectionBehavior(QTableView.SelectRows)
    win.table.verticalHeader().setVisible(False)
    win.table.horizontalHeader().setVisible(False)
    win.table.setShowGrid(False)
    win.table.setAlternatingRowColors(False)
    # Android-Studio-style dense view: one line per entry. Show only column 0
    # stretched full-width and paint the whole entry with a delegate (the model
    # stays virtualized — the delegate runs only for visible rows).
    win.table.setFont(win._make_log_font())
    win.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
    for col in range(1, len(COLUMNS)):
        win.table.setColumnHidden(col, True)
    win.log_delegate = LogItemDelegate(win)
    win.table.setItemDelegateForColumn(0, win.log_delegate)
    win.log_delegate.view = win.table
    # Copy (Ctrl+C) and Select All: keyboard shortcuts via addAction, plus a
    # custom right-click menu that also offers per-tag highlighting.
    win.copy_action = QAction("Copy", win)
    win.copy_action.setShortcut(QKeySequence.Copy)
    # Only handle Ctrl+C when the table (or a child) has focus, so a selection
    # in the detail pane copies its own text instead of the whole log line.
    win.copy_action.setShortcutContext(Qt.WidgetWithChildrenShortcut)
    win.copy_action.triggered.connect(win.copy_selection)
    win.select_all_action = QAction("Select All", win)
    win.select_all_action.triggered.connect(win.table.selectAll)
    win.bookmark_action = QAction("Toggle Bookmark", win)
    win.bookmark_action.setShortcut("Ctrl+B")
    win.bookmark_action.triggered.connect(win._toggle_bookmark)
    win.isolate_action = QAction("Isolate", win)
    win.isolate_action.setShortcut("Ctrl+I")
    win.isolate_action.triggered.connect(lambda: win._toggle_isolate(win._current_entry()))
    win.table.addAction(win.copy_action)
    win.table.addAction(win.select_all_action)
    win.table.addAction(win.bookmark_action)
    win.table.addAction(win.isolate_action)
    win.table.setContextMenuPolicy(Qt.CustomContextMenu)
    win.table.customContextMenuRequested.connect(win._show_table_menu)
    win.table.fold_toggle_requested.connect(win._on_fold_toggle_requested)

    # Detail pane: full, wrapped text of the selected row (read-only).
    win.detail = QPlainTextEdit()
    win.detail.setReadOnly(True)
    win.detail.setPlaceholderText("Select a line to see its full message here.")
    win.detail.setMaximumBlockCount(0)

    # Row 1: device + stream controls.
    win.device_box = QComboBox()
    win.device_box.setMinimumWidth(180)
    win.refresh_btn = QPushButton("Refresh")
    win.connect_btn = QPushButton("Wi-Fi…")
    win.connect_btn.setToolTip(
        "Add a device over Wi-Fi (adb connect host:port) — not the log stream control"
    )
    win.start_btn = QPushButton("Start")
    win.stop_btn = QPushButton("Stop")
    win.pause_btn = QPushButton("Pause")
    win.pause_btn.setToolTip("Pause the view (keep capturing; new lines buffer until Resume)")
    win.pause_btn.setEnabled(False)
    win.clear_btn = QPushButton("Clear")
    win.clear_device_btn = QPushButton("Clear device")
    win.clear_device_btn.setToolTip("Wipe the device's logcat buffer (adb logcat -c)")
    win.follow_check = QCheckBox("Follow")
    win.follow_check.setChecked(True)
    win.to_top_btn = QPushButton("Top")
    win.to_top_btn.setToolTip("Scroll to the oldest line")
    win.to_latest_btn = QPushButton("Latest")
    win.to_latest_btn.setToolTip("Scroll to the newest line")
    win.stop_btn.setEnabled(False)

    # Row 2: filters.
    win.package_box = QComboBox()
    win.package_box.setEditable(True)
    win.package_box.setMinimumWidth(220)
    win.package_box.lineEdit().setPlaceholderText("App, e.g. com.example.app or myapp.exe")
    win.load_pkgs_btn = QPushButton("Load")
    win.load_pkgs_btn.setToolTip("List apps seen in the log and (on Windows) currently running")
    win.apply_pkg_btn = QPushButton("Apply")
    win.clear_pkg_btn = QPushButton("Clear app")
    win.focus_app_btn = QPushButton("Browse…")
    win.focus_app_btn.setToolTip("Search running Windows processes and focus the view on one")
    win.focus_app_btn.clicked.connect(win.focus_app)

    win.level_box = QComboBox()
    for letter in LEVELS:
        win.level_box.addItem(LEVEL_NAMES[letter], letter)  # text = name, data = letter
    win.level_box.setToolTip("Minimum log level (V \u2264 D \u2264 I \u2264 W \u2264 E \u2264 F)")

    win.search = QLineEdit()
    win.search.setPlaceholderText("Filter by tag or message…")
    win.exclude = QLineEdit()
    win.exclude.setPlaceholderText("Exclude…")
    win.exclude.setToolTip("Hide lines matching this term (uses the Regex/Case toggles)")
    win.exclude.setMinimumWidth(150)
    win.match_prev_btn = QPushButton("<")
    win.match_prev_btn.setMaximumWidth(28)
    win.match_prev_btn.setToolTip("Previous match (Shift+F3)")
    win.match_next_btn = QPushButton(">")
    win.match_next_btn.setMaximumWidth(28)
    win.match_next_btn.setToolTip("Next match (F3)")
    win.match_label = QLabel("")
    win.match_label.setMinimumWidth(64)
    win.regex_check = QCheckBox("Regex")
    win.case_check = QCheckBox("Case")
    win.case_check.setToolTip("Match the search case-sensitively")
    win.search_mode_box = QComboBox()
    win.search_mode_box.addItem("Filter", "filter")
    win.search_mode_box.addItem("Highlight", "highlight")
    win.search_mode_box.setToolTip("Filter hides non-matches; Highlight tints matches")
    # Context-aware: "Save filter…" for an unsaved filter, "Update ‹name›" once a
    # saved filter is applied (see _refresh_save_update_button).
    win.save_update_btn = QPushButton("Save filter…")
    win.clear_filters_btn = QPushButton("Clear filters")
    win.clear_filters_btn.setToolTip("Reset all filters (level, search, tag, app, time…)")

    win.count_label = QLabel("0 lines")
    win.presets_list = QListWidget()
    win.presets_list.setToolTip("Double-click to apply; right-click to Add/Edit/Rename/Delete")
    win.presets_list.setContextMenuPolicy(Qt.CustomContextMenu)
    win.preset_preview = QLabel("")
    win.preset_preview.setWordWrap(True)
    win.spark_label = QLabel("")
    win.spark_label.setToolTip("Error rate over the last 500 lines")
    win.incident_label = QLabel("")
    win.incident_label.setToolTip(
        "Detected crashes/ANRs — View → Next/Previous Incident to jump to one"
    )

    # Single query bar, parsed into the filters.
    win.query = QueryLineEdit()
    win.query.setPlaceholderText("Filter — e.g. level:E tag:Activity package:com.x -noise text")
    win.query.setClearButtonEnabled(True)
    # Context-aware autocomplete (keys / level names / live tag+pid+proc values).
    # Replaces the old whole-line history completer; the query bar owns its own.
    win.query.set_context_provider(win._completion_context)


def build_layout(win) -> None:
    """Arrange the widgets built in _build_widgets into the window."""
    win._splitter = QSplitter(Qt.Vertical)
    win._splitter.addWidget(win.table)
    win._splitter.addWidget(win.detail)
    win._splitter.setStretchFactor(0, 1)
    win._splitter.setStretchFactor(1, 0)
    win._splitter.setSizes([520, 150])

    # Compact glyph buttons for the stream/device actions.
    for btn, glyph, tip in (
        (win.refresh_btn, "\u21bb", "Refresh devices"),
        (win.start_btn, "\u25b6", "Start streaming"),
        (win.stop_btn, "\u25a0", "Stop streaming"),
        (win.clear_btn, "\u2715", "Clear the log view"),
        (win.to_top_btn, "\u2912", "Scroll to the oldest line"),
        (win.to_latest_btn, "\u2913", "Scroll to the newest line"),
    ):
        btn.setText(glyph)
        btn.setToolTip(tip)
        btn.setFixedWidth(34)

    # Control bar: device/stream controls and package controls on one row,
    # split by a vertical divider (there's room, and it saves a stacked row).
    top_row = QHBoxLayout()
    top_row.addWidget(QLabel("Device:"))
    top_row.addWidget(win.device_box)
    top_row.addWidget(win.refresh_btn)
    top_row.addWidget(win.connect_btn)
    top_row.addSpacing(12)
    top_row.addWidget(win.start_btn)
    top_row.addWidget(win.stop_btn)
    top_row.addWidget(win.pause_btn)
    top_row.addWidget(win.clear_btn)
    top_row.addSpacing(12)
    top_row.addWidget(_vsep())
    top_row.addSpacing(12)
    top_row.addWidget(win.clear_device_btn)
    top_row.addWidget(win.follow_check)
    top_row.addSpacing(12)
    top_row.addWidget(win.to_top_btn)
    top_row.addWidget(win.to_latest_btn)
    top_row.addSpacing(12)
    top_row.addWidget(_vsep())
    top_row.addSpacing(12)
    top_row.addWidget(QLabel("App:"))
    top_row.addWidget(win.package_box)
    top_row.addWidget(win.load_pkgs_btn)
    top_row.addWidget(win.apply_pkg_btn)
    top_row.addWidget(win.clear_pkg_btn)
    top_row.addWidget(win.focus_app_btn)
    top_row.addSpacing(12)
    top_row.addWidget(_vsep())
    top_row.addSpacing(12)
    top_row.addWidget(QLabel("Level:"))
    top_row.addWidget(win.level_box)
    top_row.addStretch(1)

    # Filter bar: the query box on its own full-width row, plus match
    # navigation (F3/Shift+F3) feedback for the free-text portion of it.
    filter_row = QHBoxLayout()
    filter_row.addWidget(win.query)
    filter_row.addWidget(win.match_prev_btn)
    filter_row.addWidget(win.match_next_btn)
    filter_row.addWidget(win.match_label)
    filter_row.addWidget(win.save_update_btn)
    filter_row.addWidget(win.clear_filters_btn)

    win.chip_bar = FilterChipBar()
    win.chip_bar.remove_requested.connect(win._remove_query_span)

    win.histogram_bar = HistogramBar()
    win.histogram_bar.seek_requested.connect(win._seek_to_source_row)
    win.histogram_bar.hide()  # opt-in, toggled from View

    tab_row = QHBoxLayout()
    tab_row.setContentsMargins(0, 0, 0, 0)
    tab_row.setSpacing(2)
    tab_row.addWidget(win.tab_bar)
    tab_row.addWidget(win.new_tab_btn)
    tab_row.addStretch(1)

    layout = QVBoxLayout()
    layout.addLayout(tab_row)
    layout.addLayout(top_row)
    layout.addLayout(filter_row)
    layout.addWidget(win.chip_bar)
    layout.addWidget(win.histogram_bar)
    layout.addWidget(win._splitter)
    container = QWidget()
    container.setLayout(layout)
    win.setCentralWidget(container)

    panel = QWidget()
    panel_layout = QVBoxLayout(panel)
    panel_layout.setContentsMargins(6, 6, 6, 6)
    panel_layout.addWidget(QLabel("Saved Filters"))
    panel_layout.addWidget(win.presets_list)
    panel_layout.addWidget(win.preset_preview)
    # Manage presets from the list's right-click menu (Add/Edit/Rename/Delete);
    # double-click applies. Save/Update the current filter uses the filter-row button.
    win.presets_dock = QDockWidget("Saved Filters", win)
    win.presets_dock.setObjectName("presetsDock")
    win.presets_dock.setWidget(panel)
    win.addDockWidget(Qt.LeftDockWidgetArea, win.presets_dock)

    # Bookmarks dock (right side): navigable, labelable landmarks. Hidden by
    # default so the window isn't busier out of the box (open from View).
    bpanel = QWidget()
    blayout = QVBoxLayout(bpanel)
    blayout.setContentsMargins(6, 6, 6, 6)
    blayout.addWidget(QLabel("Bookmarks"))
    win.bookmarks_list = QListWidget()
    win.bookmarks_list.setToolTip("Double-click to jump; use the buttons to label or remove")
    win.bookmarks_list.itemActivated.connect(win._jump_to_bookmark_item)
    blayout.addWidget(win.bookmarks_list)
    brow = QHBoxLayout()
    win.edit_note_btn = QPushButton("Edit note…")
    win.edit_note_btn.clicked.connect(win._edit_bookmark_note)
    win.remove_bookmark_btn = QPushButton("Remove")
    win.remove_bookmark_btn.clicked.connect(win._remove_selected_bookmark)
    brow.addWidget(win.edit_note_btn)
    brow.addWidget(win.remove_bookmark_btn)
    blayout.addLayout(brow)
    win.bookmarks_dock = QDockWidget("Bookmarks", win)
    win.bookmarks_dock.setObjectName("bookmarksDock")
    win.bookmarks_dock.setWidget(bpanel)
    win.addDockWidget(Qt.RightDockWidgetArea, win.bookmarks_dock)
    win.bookmarks_dock.hide()
    win.model.bookmarksChanged.connect(win._rebuild_bookmarks_list)
    win.setStatusBar(QStatusBar())
    win.statusBar().addPermanentWidget(win.incident_label)
    win.statusBar().addPermanentWidget(win.spark_label)
    win.statusBar().addPermanentWidget(win.count_label)


def _vsep() -> QFrame:
    """A thin vertical separator that visually groups related toolbar controls."""
    line = QFrame()
    line.setFrameShape(QFrame.VLine)
    line.setFrameShadow(QFrame.Sunken)
    return line
