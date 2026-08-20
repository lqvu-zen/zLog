"""Fire-and-forget a JSON POST off the UI thread when a watch pattern hits —
see docs/plans/watch-webhook-notify.md.

Never runs inline on the UI thread: a slow/unreachable endpoint would
otherwise freeze the window for the duration of a watch hit — the same
"workers reach the UI only via signals" rule every reader in this codebase
follows, applied here to a one-shot outbound call instead of a long-lived
stream.
"""

from __future__ import annotations

import json
import urllib.request
from urllib.error import URLError

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal

_TIMEOUT = 5.0  # seconds


class _WebhookWorker(QObject, QRunnable):
    # (success, message) — message never includes the URL, since it may carry
    # a secret token (see docs/plans/watch-webhook-notify.md's Risks).
    finished = Signal(bool, str)

    def __init__(self, url: str, payload: dict):
        QObject.__init__(self)
        QRunnable.__init__(self)
        self._url = url
        self._payload = payload

    def run(self) -> None:
        try:
            data = json.dumps(self._payload).encode("utf-8")
            req = urllib.request.Request(
                self._url,
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
                status = resp.status
            self.finished.emit(True, f"HTTP {status}")
        except URLError as exc:
            self.finished.emit(False, str(exc.reason))
        except Exception as exc:  # a dead worker would otherwise fail silently
            self.finished.emit(False, str(exc))


def send_webhook(url: str, payload: dict, on_done) -> None:
    """POST `payload` as JSON to `url` on a `QThreadPool` worker thread.

    `on_done(success, message)` is connected as a normal Qt signal — since the
    caller (`MainWindow`) is a `QObject` living on the thread with the running
    event loop, Qt delivers the cross-thread call correctly on its own; no
    manual marshaling needed.
    """
    worker = _WebhookWorker(url, payload)
    worker.finished.connect(on_done)
    QThreadPool.globalInstance().start(worker)
