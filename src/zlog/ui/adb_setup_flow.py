"""adb resolution/prompt/fetch orchestration: offering to fetch adb the first
time an Android-shaped action needs it (see docs/plans/bundle-adb.md), the
Settings "Download adb…" direct path, and running the fetch itself.

Free of `MainWindow` — the two bits of state that must persist across calls
(the one-shot "already asked" flag, and the in-flight fetcher) stay owned by
the window and are threaded through as get/set callables, alongside plain
callables for the other side effects (resolving adb, reporting a status
message, saving settings, and re-resolving + refreshing devices once a fetch
completes). This module never imports `main_window`.
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QProgressDialog, QWidget

from zlog.core.adbfetch import expected_sha256, platform_tools_url
from zlog.ui.adb_fetcher import AdbFetcher
from zlog.ui.adb_setup_dialog import DOWNLOAD_PAGE, FETCH, MANUAL, ask_adb_setup

ResolveAdb = Callable[[], tuple[str, str]]
Report = Callable[[str], None]


def maybe_offer_setup(
    parent: QWidget,
    platform: str,
    resolve_adb: ResolveAdb,
    get_asked: Callable[[], bool],
    set_asked: Callable[[bool], None],
    save_settings: Callable[[], None],
    start_fetch: Callable[[str, str], None],
) -> None:
    """Offer to fetch adb the first time an Android-shaped action fails
    because adb is nowhere to be found. Fires on intent (the caller decides
    when — never at cold start) and only once until answered — a
    Windows-only user should never see this."""
    if get_asked():
        return
    _path, source = resolve_adb()
    if source != "none":
        return  # something already resolves; this failure was something else
    set_asked(True)
    save_settings()
    url = platform_tools_url(platform)
    if url is None:
        return  # fetch not offered on this OS; the status message already covers manual install
    choice = ask_adb_setup(parent)
    if choice == FETCH:
        start_fetch(url, expected_sha256(platform))
    elif choice == MANUAL:
        QDesktopServices.openUrl(QUrl(DOWNLOAD_PAGE))


def download_from_settings(
    platform: str,
    report: Report,
    start_fetch: Callable[[str, str], None],
) -> None:
    """The Settings 'Download adb…' button — a direct action, so it always
    runs regardless of the one-shot intent-triggered prompt's state."""
    url = platform_tools_url(platform)
    if url is None:
        QDesktopServices.openUrl(QUrl(DOWNLOAD_PAGE))
        report("Fetching adb isn't available on this OS — opened the download page.")
        return
    start_fetch(url, expected_sha256(platform))


def start_fetch(
    parent: QWidget,
    url: str,
    sha256: str,
    adb_data_dir: str,
    get_fetcher: Callable[[], AdbFetcher | None],
    set_fetcher: Callable[[AdbFetcher | None], None],
    report: Report,
    refresh_devices: Callable[[], None],
) -> None:
    if get_fetcher() is not None:
        report("Already downloading adb…")
        return
    dialog = QProgressDialog("Downloading adb…", "Cancel", 0, 100, parent)
    dialog.setWindowModality(Qt.WindowModal)
    dialog.setMinimumDuration(0)
    fetcher = AdbFetcher(url, sha256, adb_data_dir, parent)
    set_fetcher(fetcher)  # keep alive; also lets Settings reuse cancel later

    def on_progress(read, total):
        dialog.setValue(int(read * 100 / total) if total else 0)

    def finish():
        dialog.reset()
        set_fetcher(None)

    def on_done(_path):
        finish()
        report("adb installed.")
        refresh_devices()  # re-resolve and pick it up, no restart

    def on_error(msg):
        finish()
        report(msg)

    fetcher.progress.connect(on_progress)
    fetcher.done.connect(on_done)
    fetcher.error.connect(on_error)
    dialog.canceled.connect(fetcher.cancel)
    fetcher.start()
