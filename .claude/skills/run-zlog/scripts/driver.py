"""Headless-capable launch + screenshot driver for zLog.

Renders the running window to a PNG with ``QWidget.grab()``, which paints the
widget tree to a pixmap. That works under Qt's ``offscreen`` platform, so it needs
no physical display — handy for CI and for agents verifying a UI change.

Usage:
    uv run --with pillow python .claude/skills/run-zlog/scripts/driver.py [scenario]

Scenarios:
    smoke      (default) idle, empty window
    populated  table seeded with sample log lines
    filtered   seeded, then min-level set to Warning
    devices    device picker populated with fake devices
    package-filter  rows narrowed to a single PID (as the package filter does)
    regex-search    rows matched by a regular expression
    opened          a log loaded from saved threadtime text
    dark            the Dark theme applied to a populated table

Screenshots are written to ``../screenshots/`` next to this script.

The driver talks to the live app objects directly (``window.model``,
``window.proxy``, ``window.search``, ``window._populate_devices``), so it can reach
UI states without a device or a running ``adb``. To add a state, copy a
``scenario_*`` function, drive the widgets, call ``_shot(...)``, and register it in
``SCENARIOS``.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

# Fall back to the offscreen platform when there's no display (e.g. CI, agents).
# On Windows there's no DISPLAY/WAYLAND_DISPLAY to check, but the native "windows"
# platform doesn't reliably flush a fresh selection repaint to an invisible/
# off-screen window before grab() — it can bake a stale, illegible row into the
# pixmap no matter how long we wait. offscreen's backing store grabs correctly,
# but needs QT_QPA_FONTDIR pointed at a real font directory or it renders no text.
if sys.platform.startswith("win"):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    os.environ.setdefault("QT_QPA_FONTDIR", r"C:\Windows\Fonts")
elif (
    sys.platform.startswith("linux")
    and not os.environ.get("DISPLAY")
    and not os.environ.get("WAYLAND_DISPLAY")
):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402  (after env setup)

from zlog.core.devices import Device  # noqa: E402
from zlog.core.models import LogEntry  # noqa: E402
from zlog.ui.main_window import MainWindow  # noqa: E402

SHOTS = Path(__file__).resolve().parent.parent / "screenshots"

# A small, representative slice of logcat output covering several levels and an
# unparsed banner line, so screenshots show realistic content and row coloring.
SAMPLE = [
    LogEntry(
        "06-30 12:34:56.001",
        "1287",
        "1287",
        "I",
        "ActivityManager",
        "Start proc com.example.app for activity",
    ),
    LogEntry(
        "06-30 12:34:56.042",
        "1287",
        "1300",
        "D",
        "ViewRootImpl",
        "Relayout returned: old=[0,0][0,0]",
    ),
    LogEntry(
        "06-30 12:34:56.110",
        "1287",
        "1287",
        "W",
        "Choreographer",
        "Skipped 12 frames! The app may be doing too much work on its main thread.",
    ),
    LogEntry("06-30 12:34:56.220", "1287", "1342", "E", "AndroidRuntime", "FATAL EXCEPTION: main"),
    LogEntry(
        "06-30 12:34:56.221",
        "1287",
        "1342",
        "F",
        "AndroidRuntime",
        "Process com.example.app crashed",
    ),
    LogEntry("06-30 12:34:56.400", "980", "980", "I", "WifiService", 'Connected to network "home"'),
    LogEntry("", "", "", "", "", "--------- beginning of crash"),
]

FAKE_DEVICES = [
    Device("emulator-5554", "device"),
    Device("0A2B1C3D4E5F", "device"),
    Device("FFEE9988", "unauthorized"),
]


def _shot(window: MainWindow, name: str) -> None:
    # Let repaints fully settle before grabbing. Under the offscreen QPA platform,
    # the backing store's update-compression uses a real timer, so a tight
    # processEvents() loop with no elapsed wall-clock time can still grab a
    # mid-repaint (visually broken) frame after a selectRow()/scrollTo(). A short
    # sleep between spins gives that timer a chance to actually fire.
    for _ in range(10):
        QApplication.processEvents()
        time.sleep(0.02)
    SHOTS.mkdir(parents=True, exist_ok=True)
    path = SHOTS / f"{name}.png"
    window.grab().save(str(path))
    print(f"wrote {path}")


def _seed(window: MainWindow, repeat: int = 1) -> None:
    window.model.append_entries(SAMPLE * repeat)


def scenario_smoke(window: MainWindow) -> None:
    _shot(window, "smoke-idle")


def scenario_populated(window: MainWindow) -> None:
    _seed(window, 30)
    _shot(window, "populated")


def scenario_filtered(window: MainWindow) -> None:
    _seed(window, 30)
    window.proxy.set_min_level("W")
    _shot(window, "filtered-warn-and-above")


def scenario_devices(window: MainWindow) -> None:
    # Inject fake devices directly so no adb/device is needed.
    window._populate_devices(FAKE_DEVICES)
    _shot(window, "devices")


def scenario_package_filter(window: MainWindow) -> None:
    # Seed rows from two PIDs, then keep only one PID (as the package filter does).
    _seed(window, 8)
    window.proxy.set_pids({"1287"})
    _shot(window, "package-filter")


def scenario_package_from_log(window: MainWindow) -> None:
    # Log-driven package selector: process names come from the log (here via a
    # merged ps snapshot), Load fills the dropdown, picking one sets a proc:
    # token that filters the view — no adb, no device.
    _seed(window, 8)
    window.model.merge_process_names({"1287": "com.example.app", "980": "com.android.wifi"})
    window.load_packages()  # dropdown now holds the log's process names
    window.package_box.setEditText("com.example.app")
    window.apply_package_filter()  # -> proc:com.example.app token
    _shot(window, "package-from-log")


def scenario_regex_search(window: MainWindow) -> None:
    _seed(window, 8)
    window.proxy.set_search("Exception|Skipped", regex=True)
    _shot(window, "regex-search")


def scenario_time_range_filter(window: MainWindow) -> None:
    # SAMPLE's stamps run 12:34:56.001 -> .400; since: hides the two earliest
    # rows (and the unparseable banner line still passes through).
    _seed(window, 4)
    window._set_query_text("since:12:34:56.110")
    _shot(window, "time-range-filter")


def scenario_stack_trace_folding(window: MainWindow) -> None:
    # Seed a crash + stack frames, then fold: the header should show a ▶ glyph
    # and a "… N frames" hint, with the frames hidden below it.
    def _e(msg, lvl="E"):
        return LogEntry("06-30 12:34:56.220", "1287", "1342", lvl, "AndroidRuntime", msg)

    window.model.append_entries(
        [
            SAMPLE[0],
            _e("FATAL EXCEPTION: main"),
            _e("java.lang.RuntimeException: Unable to start activity"),
            _e("\tat android.app.ActivityThread.performLaunchActivity(ActivityThread.java:3200)"),
            _e("\tat android.app.ActivityThread.handleLaunchActivity(ActivityThread.java:3400)"),
            _e("\tat android.app.ActivityThread.-wrap11(Unknown Source:0)"),
            _e("\t... 27 more"),
            SAMPLE[6],
        ]
    )
    window.fold_action.setChecked(True)
    _shot(window, "stack-trace-folding")


def scenario_duplicate_count(window: MainWindow) -> None:
    # Seed a run of identical lines, then enable Collapse: the surviving
    # representative should show a ×N badge before its message.
    dup = LogEntry("06-30 12:00:00.000", "1287", "1287", "W", "GnssHal", "measurement dropped")
    window.model.append_entries([dup] * 6 + [SAMPLE[0]])
    window.collapse_action.setChecked(True)
    _shot(window, "duplicate-count")


def scenario_isolate(window: MainWindow) -> None:
    # Select the FATAL EXCEPTION row and isolate to it: the query bar should
    # read pid:<n> tag:AndroidRuntime, narrowing the view to just that process.
    _seed(window, 4)
    index = window.proxy.index(3, 0)
    window.table.setCurrentIndex(index)
    window._toggle_isolate(window._current_entry())
    _shot(window, "isolate")


SAMPLE_LOG_TEXT = "\n".join(
    [
        "06-30 12:34:56.001 1287 1287 I ActivityManager: Start proc com.example.app",
        "06-30 12:34:56.110 1287 1287 W Choreographer: Skipped 12 frames!",
        "06-30 12:34:56.220 1287 1342 E AndroidRuntime: FATAL EXCEPTION: main",
        "--------- beginning of crash",
    ]
)


def scenario_opened(window: MainWindow) -> None:
    from zlog.core.session import text_to_entries

    window.model.append_entries(text_to_entries(SAMPLE_LOG_TEXT))
    _shot(window, "opened")


def scenario_empty(window: MainWindow) -> None:
    window._update_placeholder()
    _shot(window, "empty")


def scenario_no_match(window: MainWindow) -> None:
    _seed(window, 4)
    window.proxy.set_search("zzz-nothing-matches", regex=False)
    window._update_placeholder()
    _shot(window, "no-match")


def scenario_two_tabs(window: MainWindow) -> None:
    # A single tab can't be closed, so its close (x) button is hidden; opening
    # a second tab should restore a real close button on both.
    _seed(window, 4)
    window._new_tab()
    _shot(window, "two-tabs")


def scenario_dark(window: MainWindow) -> None:
    window.apply_theme("Dark")
    _seed(window, 8)
    _shot(window, "dark")


def _guide_setup(window: MainWindow, dark: bool = False) -> None:
    if dark:
        window.apply_theme("Dark")
    window._populate_devices([Device("emulator-5554", "device")])
    _seed(window, 20)


def scenario_columns(window: MainWindow) -> None:
    _seed(window, 8)
    window._column_actions[1].setChecked(False)  # hide PID
    window._column_actions[2].setChecked(False)  # hide TID
    _shot(window, "columns")


def scenario_jank_summary(window: MainWindow) -> None:
    # _show_jank_summary's dialog is modal (dlg.exec() blocks), so make exec()
    # show non-modally instead — the dialog stays alive as a child of `window`
    # (QDialog(self)) even after the method returns, so it can be found and
    # grabbed like any other widget.
    from PySide6.QtWidgets import QDialog

    QDialog.exec = lambda self: (self.show(), QApplication.processEvents(), 0)[-1]

    def _jank(pid, n, t):
        return LogEntry(t, pid, "200", "W", "Choreographer", f"Skipped {n} frames!")

    window.model.append_entries(
        [
            _jank("100", 8, "06-30 12:00:00.000"),
            _jank("100", 20, "06-30 12:00:01.000"),
            _jank("200", 3, "06-30 12:00:02.000"),
        ]
    )
    window._show_jank_summary()
    dlg = window.findChildren(QDialog)[-1]
    _shot(dlg, "jank-summary")


def scenario_details(window: MainWindow) -> None:
    _seed(window, 4)
    # Select the FATAL EXCEPTION row to show its full message in the detail pane.
    index = window.proxy.index(3, 0)
    window.table.setCurrentIndex(index)
    window._update_detail(index)
    _shot(window, "details")


def scenario_highlight(window: MainWindow) -> None:
    _seed(window, 8)
    window.model.set_tag_color("Choreographer", "#b3e5fc")
    window.table.viewport().update()
    _shot(window, "highlight")


def scenario_highlight_rules(window: MainWindow) -> None:
    # A persistent rule tints every FATAL EXCEPTION row even with an unrelated
    # search active (Highlight mode, so both stay visible) — proving the rule
    # doesn't depend on what's currently in the search box.
    _seed(window, 4)
    window.model.set_highlight_rules(
        [{"pattern": "FATAL EXCEPTION", "regex": False, "color": "#ff8a80"}]
    )
    window.search_mode_box.setCurrentIndex(1)  # Highlight
    window.search.setText("WifiService")
    _shot(window, "highlight-rules")


def scenario_inline_match_highlight(window: MainWindow) -> None:
    # Seed rows, switch to Highlight mode, and search a term that appears in
    # several messages — the row tint AND the matched-substring highlight
    # inside the message should both be visible.
    _seed(window, 3)
    window.search_mode_box.setCurrentIndex(1)  # Highlight
    window.search.setText("Exception")
    _shot(window, "inline-match-highlight")


def scenario_inline_match_highlight_wrap(window: MainWindow) -> None:
    # Same as inline-match-highlight, but with wrap mode on and the window
    # narrowed so the matched message actually wraps across multiple visual
    # lines — the highlighted span must still land on the right glyphs after
    # QTextLayout re-flows the text.
    window.resize(500, 400)
    window.model.append_entries(
        [
            LogEntry(
                "06-30 12:34:56.110",
                "1287",
                "1287",
                "W",
                "Choreographer",
                "Skipped 12 frames! The app may be doing too much work on its main "
                "thread, which is a common cause of jank and dropped frames overall.",
            )
        ]
    )
    window.log_delegate.wrap = True
    window.search_mode_box.setCurrentIndex(1)  # Highlight
    window.search.setText("thread")
    _shot(window, "inline-match-highlight-wrap")


def scenario_density_compact(window: MainWindow) -> None:
    # Compact density packs rows tighter than the default (see density-modes.md).
    _seed(window, 30)
    window._set_density("compact")
    _shot(window, "density-compact")


def scenario_density_comfortable(window: MainWindow) -> None:
    _seed(window, 20)
    window._set_density("comfortable")
    _shot(window, "density-comfortable")


def scenario_wrap_refit(window: MainWindow) -> None:
    # Wrap on + a long message, then narrow the window: the row must re-fit to
    # the smaller width (grow taller) without a manual scroll — resizeEvent ->
    # _schedule_wrap_fit does it. Grab after the resize settles.
    window.model.append_entries(
        [
            LogEntry(
                "06-30 12:34:56.110",
                "1287",
                "1287",
                "W",
                "Choreographer",
                "Skipped 12 frames! The app may be doing too much work on its main "
                "thread, which is a common cause of jank and dropped frames overall, "
                "so keep heavy work off the UI thread wherever you possibly can.",
            )
        ]
    )
    window.log_delegate.wrap = True
    window._apply_row_height()
    window.resize(520, 400)
    _shot(window, "wrap-refit")


def scenario_bookmarks(window: MainWindow) -> None:
    # Seed rows, bookmark a couple, and select one so the marker is visible
    # against both a selected and unselected row.
    _seed(window, 6)
    window.model.toggle_bookmark(2)
    window.model.toggle_bookmark(9)
    index = window.proxy.index(9, 0)
    window.table.setCurrentIndex(index)
    window.table.selectRow(9)
    _shot(window, "bookmarks")


def scenario_incidents(window: MainWindow) -> None:
    # Seed a few reps of SAMPLE (each has one FATAL EXCEPTION line) so the
    # status-bar incident badge shows a nonzero count, then jump to the first
    # detected incident to show the navigation landing on it.
    _seed(window, 3)
    window._goto_incident(1)
    _shot(window, "incidents")


def scenario_match_nav(window: MainWindow) -> None:
    # Seed rows, search for a term that matches several, and step to one match
    # so the match label ("n/total") and row selection are both visible.
    _seed(window, 6)
    window.search.setText("Exception")
    window._goto_match(1)
    _shot(window, "match-nav")


def scenario_copy(window: MainWindow) -> None:
    # Seed rows, filter to W+ so the proxy shows a subset, select all visible rows,
    # and print the copied text to prove proxy->source mapping respects the filter.
    _seed(window, 2)
    window.proxy.set_min_level("W")
    window.table.selectAll()
    print("COPIED TEXT >>>")
    print(window._selected_text(), end="")
    print("<<< END")
    _shot(window, "copy")


def scenario_guide_streaming(window: MainWindow) -> None:
    _guide_setup(window)
    window.statusBar().showMessage("Streaming adb logcat (emulator-5554)…  1,204 lines")
    _shot(window, "guide-streaming")


def scenario_guide_dark(window: MainWindow) -> None:
    _guide_setup(window, dark=True)
    window.statusBar().showMessage("Streaming adb logcat (emulator-5554)…  1,204 lines")
    _shot(window, "guide-dark")


def scenario_guide_level(window: MainWindow) -> None:
    _guide_setup(window)
    window.level_box.setCurrentText("W")
    window.proxy.set_min_level("W")
    window.statusBar().showMessage("Showing Warning and above.")
    _shot(window, "guide-level")


def scenario_guide_package(window: MainWindow) -> None:
    _guide_setup(window)
    window.package_box.setEditText("com.example.app")
    window.proxy.set_pids({"1287"})
    window.statusBar().showMessage("Showing com.example.app (pid 1287).")
    _shot(window, "guide-package")


SCENARIOS = {
    "smoke": scenario_smoke,
    "populated": scenario_populated,
    "filtered": scenario_filtered,
    "devices": scenario_devices,
    "package-filter": scenario_package_filter,
    "package-from-log": scenario_package_from_log,
    "regex-search": scenario_regex_search,
    "time-range-filter": scenario_time_range_filter,
    "isolate": scenario_isolate,
    "duplicate-count": scenario_duplicate_count,
    "stack-trace-folding": scenario_stack_trace_folding,
    "opened": scenario_opened,
    "two-tabs": scenario_two_tabs,
    "dark": scenario_dark,
    "empty": scenario_empty,
    "no-match": scenario_no_match,
    "copy": scenario_copy,
    "bookmarks": scenario_bookmarks,
    "incidents": scenario_incidents,
    "match-nav": scenario_match_nav,
    "highlight": scenario_highlight,
    "highlight-rules": scenario_highlight_rules,
    "jank-summary": scenario_jank_summary,
    "inline-match-highlight": scenario_inline_match_highlight,
    "inline-match-highlight-wrap": scenario_inline_match_highlight_wrap,
    "wrap-refit": scenario_wrap_refit,
    "density-compact": scenario_density_compact,
    "density-comfortable": scenario_density_comfortable,
    "details": scenario_details,
    "columns": scenario_columns,
    "guide-streaming": scenario_guide_streaming,
    "guide-dark": scenario_guide_dark,
    "guide-level": scenario_guide_level,
    "guide-package": scenario_guide_package,
}


def main() -> int:
    name = sys.argv[1] if len(sys.argv) > 1 else "smoke"
    if name not in SCENARIOS:
        print(f"unknown scenario {name!r}; choose from: {', '.join(SCENARIOS)}")
        return 2
    app = QApplication(sys.argv[:1])
    window = MainWindow()
    window.resize(1100, 700)
    window.show()
    app.processEvents()
    SCENARIOS[name](window)
    return 0


if __name__ == "__main__":
    sys.exit(main())
