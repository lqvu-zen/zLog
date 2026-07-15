"""Application entry point. `zlog` (console script) and `python -m zlog`
both call main()."""

from __future__ import annotations

import platform
import sys

from PySide6 import __version__ as _pyside_version
from PySide6.QtCore import (
    QStandardPaths,
    QtMsgType,
    qInstallMessageHandler,
    qVersion,
)
from PySide6.QtWidgets import QApplication

from zlog import __version__
from zlog.core import applog
from zlog.ui.main_window import MainWindow

_QT_MSG_LEVEL = {
    QtMsgType.QtDebugMsg: 10,  # logging.DEBUG
    QtMsgType.QtInfoMsg: 20,  # logging.INFO
    QtMsgType.QtWarningMsg: 30,  # logging.WARNING
    QtMsgType.QtCriticalMsg: 40,  # logging.ERROR
    QtMsgType.QtFatalMsg: 50,  # logging.CRITICAL
}


def _config_dir() -> str:
    """Same per-user config dir the settings live in (so zlog.log sits beside
    settings.json)."""
    return QStandardPaths.writableLocation(QStandardPaths.AppConfigLocation) or "."


def _install_excepthook() -> None:
    """Log uncaught exceptions to the diagnostics file, then chain to the previous
    hook so behavior (and test runners) aren't swallowed."""
    previous = sys.excepthook

    def hook(exc_type, exc, tb):
        applog.get_logger().critical("Uncaught exception", exc_info=(exc_type, exc, tb))
        previous(exc_type, exc, tb)

    sys.excepthook = hook


def _install_qt_message_handler() -> None:
    """Route Qt's own warnings/messages into the diagnostics log."""
    logger = applog.get_logger()

    def handler(mode, context, message):
        logger.log(_QT_MSG_LEVEL.get(mode, 20), "Qt: %s", message)

    qInstallMessageHandler(handler)


def main() -> int:
    app = QApplication(sys.argv)
    # Names give QStandardPaths a proper per-user config dir for settings + the log.
    app.setApplicationName("zlog")
    app.setOrganizationName("zlog")

    applog.configure(_config_dir())
    _install_excepthook()
    _install_qt_message_handler()
    applog.get_logger().info(
        "zLog %s starting — Python %s, PySide6 %s / Qt %s, %s",
        __version__,
        platform.python_version(),
        _pyside_version,
        qVersion(),
        platform.platform(),
    )

    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
