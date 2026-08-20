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


# `QRunnable.autoDelete()` defaults to True: QThreadPool deletes the C++ side of
# the runnable the instant `run()` returns. Since `_WebhookWorker` is the *same*
# object on both its QObject and QRunnable sides, that delete fires before the
# `finished` signal (queued, cross-thread) has been delivered to the main
# thread — a real, reproducible use-after-free (`Fatal Python error: Aborted`
# deep in shiboken/Qt) once the queued event is processed. `setAutoDelete(False)`
# plus keeping every in-flight worker alive here in `_inflight` (nothing else
# holds a Python reference once `send_webhook` returns) fixes both halves of
# that lifetime bug at once.
_inflight: set = set()


def send_webhook(url: str, payload: dict, on_done) -> None:
    """POST `payload` as JSON to `url` on a `QThreadPool` worker thread.

    `on_done(success, message)` is connected as a normal Qt signal — since the
    caller (`MainWindow`) is a `QObject` living on the thread with the running
    event loop, Qt delivers the cross-thread call correctly on its own; no
    manual marshaling needed.
    """
    worker = _WebhookWorker(url, payload)
    worker.setAutoDelete(False)  # see the module-level note above `_inflight`
    _inflight.add(worker)

    def _finish(success: bool, message: str) -> None:
        _inflight.discard(worker)
        on_done(success, message)

    worker.finished.connect(_finish)
    QThreadPool.globalInstance().start(worker)
