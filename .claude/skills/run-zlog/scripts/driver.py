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
from pathlib import Path

# Fall back to the offscreen platform when there's no display (e.g. CI, agents).
if (
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
    QApplication.processEvents()  # let layout/geometry settle before grabbing
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


def scenario_regex_search(window: MainWindow) -> None:
    _seed(window, 8)
    window.proxy.set_search("Exception|Skipped", regex=True)
    _shot(window, "regex-search")


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


def scenario_dark(window: MainWindow) -> None:
    window.apply_theme("Dark")
    _seed(window, 8)
    _shot(window, "dark")


def _guide_setup(window: MainWindow, dark: bool = False) -> None:
    if dark:
        window.apply_theme("Dark")
    window._populate_devices([Device("emulator-5554", "device")])
    _seed(window, 20)


def scenario_highlight(window: MainWindow) -> None:
    _seed(window, 8)
    window.model.set_tag_color("Choreographer", "#b3e5fc")
    window.table.viewport().update()
    _shot(window, "highlight")


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
    "regex-search": scenario_regex_search,
    "opened": scenario_opened,
    "dark": scenario_dark,
    "empty": scenario_empty,
    "no-match": scenario_no_match,
    "copy": scenario_copy,
    "highlight": scenario_highlight,
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
