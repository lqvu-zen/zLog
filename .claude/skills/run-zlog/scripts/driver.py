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

Screenshots are written to ``../screenshots/`` next to this script.

The driver talks to the live app objects directly (``window.model``,
``window.proxy``, ``window.search``), so it can reach UI states without a device
or a running ``adb``. To add a state, copy a ``scenario_*`` function, drive the
widgets, call ``_shot(...)``, and register it in ``SCENARIOS``.
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


SCENARIOS = {
    "smoke": scenario_smoke,
    "populated": scenario_populated,
    "filtered": scenario_filtered,
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
