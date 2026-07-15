"""zLog's own diagnostics log — the app logging *its own* behavior to a file so a
freeze, an adb failure, or a crash can be diagnosed after the fact (including in
the frozen .exe build, where there is no console).

Pure stdlib, no Qt, so `core` stays Qt-free and this is unit-testable. The UI
decides *where* the file lives (an OS config dir) and calls `configure()` once at
startup; everything else just does `logging.getLogger("zlog")`.
"""

from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler

LOGGER_NAME = "zlog"
_LOG_FILENAME = "zlog.log"
_MAX_BYTES = 1_000_000  # ~1 MB per file
_BACKUP_COUNT = 3  # zlog.log + zlog.log.1..3
_DEFAULT_LEVEL = "INFO"


def log_path(log_dir: str) -> str:
    """Absolute path of the diagnostics log file inside `log_dir`."""
    return os.path.join(log_dir, _LOG_FILENAME)


def _resolve_level(level: str | None) -> int:
    """Level from the explicit arg, else the ZLOG_LOG_LEVEL env, else INFO.

    Tolerant of junk (unknown names / numbers fall back to INFO) so a stray env
    value can never stop logging from starting.
    """
    name = (level or os.environ.get("ZLOG_LOG_LEVEL") or _DEFAULT_LEVEL).strip().upper()
    resolved = logging.getLevelName(name)
    return resolved if isinstance(resolved, int) else logging.INFO


def get_logger() -> logging.Logger:
    """The shared `zlog` logger. Safe to call before `configure()`."""
    return logging.getLogger(LOGGER_NAME)


def configure(log_dir: str, level: str | None = None) -> str | None:
    """Attach a rotating file handler for the `zlog` logger under `log_dir`.

    Idempotent: calling it again won't add a second file handler. Never raises —
    if the directory can't be created or opened (read-only, permissions), logging
    silently degrades to no file handler instead of crashing startup. Returns the
    log file path on success, else None.
    """
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(_resolve_level(level))
    logger.propagate = False  # don't double-log through the root logger

    path = log_path(log_dir)
    # Idempotent: bail if we already added a handler for this exact file.
    for handler in logger.handlers:
        if (
            isinstance(handler, RotatingFileHandler)
            and getattr(handler, "_zlog_path", None) == path
        ):
            handler.setLevel(logger.level)
            return path

    try:
        os.makedirs(log_dir, exist_ok=True)
        handler = RotatingFileHandler(
            path, maxBytes=_MAX_BYTES, backupCount=_BACKUP_COUNT, encoding="utf-8"
        )
    except OSError:
        return None  # degrade gracefully — the app still runs, just no file log

    handler._zlog_path = path  # tag so a repeat configure() is a no-op
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)-7s %(name)s: %(message)s"))
    logger.addHandler(handler)
    return path
