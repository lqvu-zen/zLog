"""`send_webhook` against a real local HTTP server (loopback, ephemeral port —
no external network), so the actual POST/threading path is exercised rather
than mocked. Mirrors tests/test_net_reader.py's approach of using a real
socket-backed resource.
"""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from PySide6.QtCore import QEventLoop, QTimer

from zlog.ui.webhook_sender import send_webhook


def _wait_for(qapp, predicate, timeout_ms=6000):
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


class _CapturingHandler(BaseHTTPRequestHandler):
    received: list = []

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        type(self).received.append(
            {"body": json.loads(body), "content_type": self.headers.get("Content-Type")}
        )
        self.send_response(200)
        self.end_headers()

    def log_message(self, *args):  # silence the default stderr access log
        pass


def _start_server():
    _CapturingHandler.received = []
    server = HTTPServer(("127.0.0.1", 0), _CapturingHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


def test_send_webhook_posts_json_body(qapp):
    server, thread = _start_server()
    try:
        url = f"http://127.0.0.1:{server.server_port}/hook"
        results = []
        send_webhook(url, {"message": "hello"}, lambda ok, msg: results.append((ok, msg)))

        assert _wait_for(qapp, lambda: len(results) >= 1)
        success, message = results[0]
        assert success is True
        assert "200" in message
        assert _CapturingHandler.received == [
            {"body": {"message": "hello"}, "content_type": "application/json"}
        ]
    finally:
        server.shutdown()
        thread.join(timeout=2)


def test_send_webhook_unreachable_reports_failure_without_blocking(qapp):
    # Nothing is listening on this port (it was just bound-and-released), so
    # the connection is refused quickly rather than hanging.
    probe = HTTPServer(("127.0.0.1", 0), _CapturingHandler)
    dead_port = probe.server_port
    probe.server_close()

    results = []
    send_webhook(
        f"http://127.0.0.1:{dead_port}/hook",
        {"message": "x"},
        lambda ok, msg: results.append((ok, msg)),
    )
    assert _wait_for(qapp, lambda: len(results) >= 1)
    success, message = results[0]
    assert success is False
    assert message  # some failure reason, never blocked the caller to get it
