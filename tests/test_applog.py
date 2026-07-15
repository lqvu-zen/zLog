"""Tests for the self-diagnostics logging setup (pure stdlib, no Qt)."""

from __future__ import annotations

import logging

from zlog.core import applog


def _reset() -> None:
    """Detach any handlers so each test starts from a clean logger."""
    logger = logging.getLogger(applog.LOGGER_NAME)
    for h in list(logger.handlers):
        h.close()
        logger.removeHandler(h)


def test_configure_creates_file_and_writes(tmp_path, monkeypatch):
    _reset()
    monkeypatch.delenv("ZLOG_LOG_LEVEL", raising=False)
    path = applog.configure(str(tmp_path))
    assert path == applog.log_path(str(tmp_path))

    applog.get_logger().info("hello-diagnostics")
    for h in logging.getLogger(applog.LOGGER_NAME).handlers:
        h.flush()
    assert "hello-diagnostics" in (tmp_path / "zlog.log").read_text(encoding="utf-8")
    _reset()


def test_configure_is_idempotent(tmp_path, monkeypatch):
    _reset()
    monkeypatch.delenv("ZLOG_LOG_LEVEL", raising=False)
    applog.configure(str(tmp_path))
    applog.configure(str(tmp_path))  # second call must not add a duplicate handler
    file_handlers = [
        h
        for h in logging.getLogger(applog.LOGGER_NAME).handlers
        if getattr(h, "_zlog_path", None) is not None
    ]
    assert len(file_handlers) == 1
    _reset()


def test_level_honors_env(tmp_path, monkeypatch):
    _reset()
    monkeypatch.setenv("ZLOG_LOG_LEVEL", "warning")
    applog.configure(str(tmp_path))
    assert logging.getLogger(applog.LOGGER_NAME).level == logging.WARNING
    _reset()


def test_bad_env_level_falls_back_to_info(tmp_path, monkeypatch):
    _reset()
    monkeypatch.setenv("ZLOG_LOG_LEVEL", "not-a-level")
    applog.configure(str(tmp_path))
    assert logging.getLogger(applog.LOGGER_NAME).level == logging.INFO
    _reset()


def test_unwritable_dir_degrades_without_raising(tmp_path, monkeypatch):
    _reset()
    monkeypatch.delenv("ZLOG_LOG_LEVEL", raising=False)
    # A path whose parent is a file, not a dir — makedirs will fail; must not raise.
    blocker = tmp_path / "afile"
    blocker.write_text("x", encoding="utf-8")
    assert applog.configure(str(blocker / "sub")) is None
    _reset()
