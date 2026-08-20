"""NetworkReader against a real loopback TCP connection: no external network,
so this is fast and safe in CI. Mirrors tests/test_file_follower.py's approach
of exercising the actual read loop rather than only pure helpers.
"""

from __future__ import annotations

import socket

from PySide6.QtCore import QEventLoop, QTimer

from zlog.net.reader import NetworkReader, should_flush


def _messages(entries):
    return [e.message for e in entries]


def _wait_for(qapp, predicate, timeout_ms=6000):
    """Spin the event loop until `predicate()` or the timeout (never hang CI)."""
    loop = QEventLoop()
    elapsed = {"ms": 0}

    def tick():
        elapsed["ms"] += 50
        if predicate() or elapsed["ms"] >= timeout_ms:
            loop.quit()

    timer = QTimer()
    timer.timeout.connect(tick)
    timer.start(50)
    loop.exec()
    timer.stop()
    return predicate()


def _start(qapp):
    reader = NetworkReader("127.0.0.1", 0)  # ephemeral port: no test ever collides
    got: list = []
    errors: list = []
    ports: list = []
    reader.batch_ready.connect(got.extend)
    reader.error.connect(errors.append)
    reader.listening.connect(ports.append)
    reader.start()
    return reader, got, errors, ports


def test_resolves_an_ephemeral_port_and_streams_a_connection(qapp):
    reader, got, _errors, ports = _start(qapp)
    try:
        assert _wait_for(qapp, lambda: len(ports) >= 1)
        port = ports[0]
        assert port > 0
        assert reader.port == port

        client = socket.create_connection(("127.0.0.1", port), timeout=2)
        try:
            client.sendall(b"06-30 12:00:00.000 1 2 I Tag: line1\n")
            assert _wait_for(qapp, lambda: len(got) >= 1)
            assert "line1" in _messages(got)[0]
        finally:
            client.close()
    finally:
        reader.stop()


def test_partial_line_across_two_sends_is_one_entry(qapp):
    reader, got, _errors, ports = _start(qapp)
    try:
        assert _wait_for(qapp, lambda: len(ports) >= 1)
        client = socket.create_connection(("127.0.0.1", ports[0]), timeout=2)
        try:
            client.sendall(b"06-30 12:00:00.000 1 2 I Tag: ")
            client.sendall(b"split across two sends\n")
            assert _wait_for(qapp, lambda: len(got) >= 1)
            assert len(got) == 1
            assert got[0].message == "split across two sends"
        finally:
            client.close()
    finally:
        reader.stop()


def test_second_connection_is_rejected_not_queued(qapp):
    reader, got, errors, ports = _start(qapp)
    try:
        assert _wait_for(qapp, lambda: len(ports) >= 1)
        port = ports[0]
        first = socket.create_connection(("127.0.0.1", port), timeout=2)
        second = socket.create_connection(("127.0.0.1", port), timeout=2)
        try:
            assert _wait_for(qapp, lambda: len(errors) >= 1)
            assert "Rejected" in errors[0]

            # The first connection is unaffected by the rejection.
            first.sendall(b"06-30 12:00:00.000 1 2 I Tag: still alive\n")
            assert _wait_for(qapp, lambda: len(got) >= 1)
            assert "still alive" in _messages(got)[0]
        finally:
            first.close()
            second.close()
    finally:
        reader.stop()


def test_reconnect_after_disconnect_is_accepted(qapp):
    reader, got, _errors, ports = _start(qapp)
    try:
        assert _wait_for(qapp, lambda: len(ports) >= 1)
        port = ports[0]
        first = socket.create_connection(("127.0.0.1", port), timeout=2)
        first.sendall(b"06-30 12:00:00.000 1 2 I Tag: first\n")
        assert _wait_for(qapp, lambda: len(got) >= 1)
        first.close()

        second = socket.create_connection(("127.0.0.1", port), timeout=2)
        try:
            second.sendall(b"06-30 12:00:00.000 1 2 I Tag: second\n")
            assert _wait_for(qapp, lambda: len(got) >= 2)
            assert "second" in _messages(got)[1]
        finally:
            second.close()
    finally:
        reader.stop()


def test_bind_failure_reports_error(qapp):
    blocker = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    blocker.bind(("127.0.0.1", 0))
    blocker.listen(1)
    busy_port = blocker.getsockname()[1]
    try:
        reader = NetworkReader("127.0.0.1", busy_port)
        errors = []
        reader.error.connect(errors.append)
        reader.start()
        try:
            assert _wait_for(qapp, lambda: len(errors) >= 1)
            assert "Could not listen" in errors[0]
        finally:
            reader.stop()
    finally:
        blocker.close()


def test_stop_ends_the_thread_promptly(qapp):
    reader, _got, _errors, ports = _start(qapp)
    assert _wait_for(qapp, lambda: len(ports) >= 1)
    reader.stop()
    assert not reader.isRunning()


def test_should_flush_rules():
    assert should_flush(0, 999) is False
    assert should_flush(1, 0.0) is False
    assert should_flush(500, 0.0) is True
    assert should_flush(1, 0.2) is True
