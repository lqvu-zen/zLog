"""Menu-bar construction for :class:`~zlog.ui.main_window.MainWindow`.

Split out of the window (see docs/plans/main-window-split.md). `build_menus(win)`
creates the File/View/Help menus and stores the actions it creates on the window
(`win.redact_action`, `win.details_action`, `win.capture_debug_act`, …), so the
window and the tests reach them exactly as before.
"""

from __future__ import annotations

from PySide6.QtGui import QAction, QActionGroup

from zlog.core.export import to_csv, to_html, to_json
from zlog.ui.theme import THEMES


def build_menus(win) -> None:
    """Build the File and View menus (their actions wire themselves here)."""
    file_menu = win.menuBar().addMenu("&File")
    new_window_act = file_menu.addAction("New &Window")
    new_window_act.setShortcut("Ctrl+Shift+N")
    new_window_act.triggered.connect(win._new_window)
    new_tab_act = file_menu.addAction("New &Tab")
    new_tab_act.setShortcut("Ctrl+T")
    new_tab_act.triggered.connect(win._new_tab)
    file_menu.addSeparator()
    open_act = file_menu.addAction("&Open Log…")
    open_act.setShortcut("Ctrl+O")
    open_act.triggered.connect(win.open_log)
    win._recent_menu = file_menu.addMenu("Open &Recent")
    follow_act = file_menu.addAction("&Follow File…")
    follow_act.setToolTip("Watch a log file and stream new lines as they're written")
    follow_act.triggered.connect(win.follow_file)
    win._rebuild_recent_menu()
    save_act = file_menu.addAction("&Save Log…")
    save_act.setShortcut("Ctrl+S")
    save_act.triggered.connect(win.save_log)
    save_filtered_act = file_menu.addAction("Save &Filtered Log…")
    save_filtered_act.triggered.connect(win.save_filtered_log)

    file_menu.addSeparator()
    save_session_act = file_menu.addAction("Save Sess&ion…")
    save_session_act.triggered.connect(win.save_session)
    open_session_act = file_menu.addAction("Open Se&ssion…")
    open_session_act.triggered.connect(win.open_session)
    diff_act = file_menu.addAction("&Diff Against File…")
    diff_act.triggered.connect(win._diff_against_file)
    # Kept on the window: it's adb-only, so it greys out for a local source.
    win.dumpsys_act = file_menu.addAction("Capture &dumpsys…")
    win.dumpsys_act.triggered.connect(win._capture_dumpsys)
    merged_act = file_menu.addAction("&Merge All Devices")
    merged_act.triggered.connect(win.start_merged)
    # Same code path as picking "This PC" in the device box and pressing Start;
    # kept as a shortcut for people who know it by name.
    win.capture_debug_act = file_menu.addAction("Capture Debug &Output (This PC)")
    win.capture_debug_act.setToolTip(
        "Same as choosing 'This PC' in the device box and pressing Start — "
        "captures OutputDebugString; filter to your app with proc: / pid:"
    )
    win.capture_debug_act.triggered.connect(win.capture_debug_output)
    win.launch_app_act = file_menu.addAction("&Launch App…")
    win.launch_app_act.setToolTip(
        "Start a program and capture its console output (and its Windows "
        "debug output) from the first line"
    )
    win.launch_app_act.triggered.connect(win.launch_app)
    file_menu.addSeparator()
    win.redact_action = QAction("Redact secrets", win)
    win.redact_action.setCheckable(True)
    win.redact_action.setToolTip("Mask emails, IPs, and tokens when saving or exporting")
    export_menu = file_menu.addMenu("&Export")
    export_menu.addAction(win.redact_action)  # opt-in masking for every save/export
    export_menu.addSeparator()
    for name, fmt, ext in (
        ("CSV", to_csv, "csv"),
        ("JSON", to_json, "json"),
        ("HTML", to_html, "html"),
    ):
        act = export_menu.addAction(f"{name}…")
        act.triggered.connect(lambda _checked=False, n=name, f=fmt, e=ext: win._export(n, f, e))

    view_menu = win.menuBar().addMenu("&View")

    # Preference actions are created here as standalone objects (the state the
    # Settings dialog reads/writes) but are NOT put in the View menu — the View
    # menu keeps only commands + navigation. See _build_menus / settings_dialog.
    win._theme_group = QActionGroup(win)
    win._theme_group.setExclusive(True)
    for name in THEMES:
        act = QAction(name, win)
        act.setCheckable(True)
        act.setChecked(name == "Light")
        win._theme_group.addAction(act)
        act.triggered.connect(lambda _checked=False, n=name: win.apply_theme(n))

    win.details_action = QAction("Show Details", win)
    win.details_action.setCheckable(True)
    win.details_action.setChecked(True)
    win.details_action.toggled.connect(win.detail.setVisible)
    win.clear_on_start_action = QAction("Clear on Start", win)
    win.clear_on_start_action.setCheckable(True)
    # Kept as `reopen_last_action` (and the `reopen_last` settings key) so existing
    # settings files keep working; it now restores every tab, not just the last log.
    win.reopen_last_action = QAction("Restore Tabs on Launch", win)
    win.reopen_last_action.setCheckable(True)
    win.reopen_last_action.setToolTip("Reopen the tabs and filters you had open last time")
    win.autosave_action = QAction("Autosave Capture", win)
    win.autosave_action.setCheckable(True)
    win.autosave_action.toggled.connect(win._on_autosave_toggled)
    win.process_action = QAction("Show Process Names", win)
    win.process_action.setCheckable(True)
    win.process_action.toggled.connect(win._on_process_toggled)
    win.collapse_action = QAction("Collapse Repeated Lines", win)
    win.collapse_action.setCheckable(True)
    win.collapse_action.toggled.connect(win._on_collapse_toggled)
    win.fold_action = QAction("Fold Stack Traces", win)
    win.fold_action.setCheckable(True)
    win.fold_action.toggled.connect(win._on_fold_toggled)
    win.case_action = QAction("Case sensitive", win)
    win.case_action.setCheckable(True)
    win.case_action.toggled.connect(win._on_case_toggled)
    win.highlight_action = QAction("Highlight matches", win)
    win.highlight_action.setCheckable(True)
    win.highlight_action.toggled.connect(win._on_highlight_toggled)

    win._time_group = QActionGroup(win)
    win._time_group.setExclusive(True)
    win._time_actions = {}
    for mode, label in (
        ("absolute", "Absolute"),
        ("since_start", "Since start"),
        ("delta", "Delta"),
    ):
        act = QAction(label, win)
        act.setCheckable(True)
        act.setChecked(mode == "absolute")
        win._time_group.addAction(act)
        act.triggered.connect(lambda _c=False, m=mode: win.model.set_time_mode(m))
        win._time_actions[mode] = act

    win._buffer_actions = {}
    for name in ("main", "system", "crash", "radio", "events", "kernel"):
        act = QAction(name, win)
        act.setCheckable(True)
        win._buffer_actions[name] = act

    win._tail_group = QActionGroup(win)
    win._tail_group.setExclusive(True)
    win._tail_actions = {}
    for count, label in (
        (0, "Whole buffer"),
        (500, "Last 500"),
        (1000, "Last 1000"),
        (5000, "Last 5000"),
        (10000, "Last 10,000"),
    ):
        act = QAction(label, win)
        act.setCheckable(True)
        act.setChecked(count == 0)
        win._tail_group.addAction(act)
        win._tail_actions[count] = act

    # --- command / navigation items (these stay in the View menu) ---
    clear_filters_act = view_menu.addAction("Clear F&ilters")
    clear_filters_act.triggered.connect(win.clear_filters)
    next_problem_act = view_menu.addAction("Next Problem")
    next_problem_act.setShortcut("F2")
    next_problem_act.triggered.connect(lambda: win._goto_severity(1))
    prev_problem_act = view_menu.addAction("Previous Problem")
    prev_problem_act.setShortcut("Shift+F2")
    prev_problem_act.triggered.connect(lambda: win._goto_severity(-1))
    tag_summary_act = view_menu.addAction("&Tag Summary…")
    tag_summary_act.triggered.connect(win._show_tag_summary)
    jank_summary_act = view_menu.addAction("&Jank Summary…")
    jank_summary_act.triggered.connect(win._show_jank_summary)
    extract_act = view_menu.addAction("&Extract Fields…")
    extract_act.triggered.connect(win._edit_extractors)
    highlight_rules_act = view_menu.addAction("&Highlight Rules…")
    highlight_rules_act.triggered.connect(win._show_highlight_rules_dialog)
    view_menu.addAction(win.fold_action)  # Fold Stack Traces (checkable)
    watch_act = view_menu.addAction("Set &Watch…")
    watch_act.triggered.connect(win._set_watch_dialog)
    reload_plugins_act = view_menu.addAction("Reload &Plugins")
    reload_plugins_act.triggered.connect(win._load_plugins)
    view_menu.addAction(win.presets_dock.toggleViewAction())
    view_menu.addAction(win.bookmarks_dock.toggleViewAction())
    win.histogram_action = QAction("Show &Timeline", win)
    win.histogram_action.setCheckable(True)
    win.histogram_action.toggled.connect(win._on_histogram_toggled)
    view_menu.addAction(win.histogram_action)
    win.sticky_action = QAction("Pin Anchor &Line", win)
    win.sticky_action.setCheckable(True)
    win.sticky_action.toggled.connect(win._on_sticky_toggled)
    view_menu.addAction(win.sticky_action)
    win.presets_menu = view_menu.addMenu("Filter &Presets")
    win._rebuild_presets_menu()

    view_menu.addSeparator()
    next_bm = view_menu.addAction("Next Bookmark")
    next_bm.setShortcut("Ctrl+F2")
    next_bm.triggered.connect(lambda: win._goto_bookmark(1))
    prev_bm = view_menu.addAction("Previous Bookmark")
    prev_bm.setShortcut("Ctrl+Shift+F2")
    prev_bm.triggered.connect(lambda: win._goto_bookmark(-1))
    clear_bm = view_menu.addAction("Clear Bookmarks")
    clear_bm.triggered.connect(win._clear_bookmarks)

    view_menu.addSeparator()
    next_incident = view_menu.addAction("Next Incident")
    next_incident.setShortcut("Alt+F2")
    next_incident.triggered.connect(lambda: win._goto_incident(1))
    prev_incident = view_menu.addAction("Previous Incident")
    prev_incident.setShortcut("Alt+Shift+F2")
    prev_incident.triggered.connect(lambda: win._goto_incident(-1))

    view_menu.addSeparator()
    zoom_in = view_menu.addAction("Zoom In")
    zoom_in.setShortcut("Ctrl+=")
    zoom_in.triggered.connect(lambda: win._zoom(1))
    zoom_out = view_menu.addAction("Zoom Out")
    zoom_out.setShortcut("Ctrl+-")
    zoom_out.triggered.connect(lambda: win._zoom(-1))
    zoom_reset = view_menu.addAction("Reset Zoom")
    zoom_reset.setShortcut("Ctrl+0")
    zoom_reset.triggered.connect(win._reset_zoom)

    clear_buf_act = view_menu.addAction("Clear device log &buffer")
    clear_buf_act.triggered.connect(win._clear_device_buffer)

    win._settings_act = win.menuBar().addAction("&Settings…")
    win._settings_act.triggered.connect(win._open_settings)

    help_menu = win.menuBar().addMenu("&Help")
    win.open_log_action = QAction("Open &Log Folder", win)
    win.open_log_action.triggered.connect(win._open_log_folder)
    help_menu.addAction(win.open_log_action)
