"""The one-time "adb is missing" prompt (see docs/plans/bundle-adb.md).

Fires on Android intent (Refresh, Wi-Fi Connect, Capture dumpsys…) the first
time adb resolves to nothing at all — never at cold start, and never for
someone who only uses the Windows/local sources, since they have no use for
adb and would just be nagged about tooling they don't need.
"""

from __future__ import annotations

from PySide6.QtWidgets import QMessageBox, QWidget

#: Where "I'll do it myself" points — the same page linked from the README.
DOWNLOAD_PAGE = "https://developer.android.com/tools/releases/platform-tools"

FETCH = "fetch"  # let zLog download it
MANUAL = "manual"  # the user will install it themselves
LATER = "later"  # dismissed; Settings -> Download adb... remains the way back in


def ask_adb_setup(parent: QWidget | None) -> str:
    """Show the prompt and return the user's choice (FETCH / MANUAL / LATER).
    Plain and skippable, not a wizard — a single dialog with three ways out."""
    box = QMessageBox(parent)
    box.setWindowTitle("adb not found")
    box.setIcon(QMessageBox.Icon.Question)
    box.setText("zLog needs Android's adb tool to talk to a device.")
    box.setInformativeText(
        "zLog can download it for you now (Google's official platform-tools, "
        "~10 MB), or you can point Settings at a copy you install yourself.\n\n"
        "This only matters for Android devices — This PC (debug output), "
        "Launch App…, and Follow File… all work without it."
    )
    fetch_btn = box.addButton("Download for me", QMessageBox.ButtonRole.AcceptRole)
    manual_btn = box.addButton("I'll do it myself", QMessageBox.ButtonRole.ActionRole)
    box.addButton("Not now", QMessageBox.ButtonRole.RejectRole)
    box.setDefaultButton(fetch_btn)
    box.exec()
    clicked = box.clickedButton()
    if clicked is fetch_btn:
        return FETCH
    if clicked is manual_btn:
        return MANUAL
    return LATER
