"""Application entry point. `zlog` (console script) and `python -m zlog`
both call main()."""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from zlog.ui.main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    # Names give QStandardPaths a proper per-user config dir for settings.
    app.setApplicationName("zlog")
    app.setOrganizationName("zlog")
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
