"""Where to find `adb` — pure resolution logic, no Qt and no real filesystem
calls (those are injected), so it's unit-testable (see docs/plans/bundle-adb.md).
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import PurePosixPath, PureWindowsPath

#: One resolved (path, source) pair. `source` is one of "setting" (an explicit
#: Settings → adb path), "path" (found on PATH), "managed" (a copy zLog fetched
#: itself), or "none" (nothing found anywhere — `path` falls back to the bare
#: "adb" command so a missing adb still fails the same clear way as always).
AdbLocation = tuple[str, str]


def resolve_adb(
    setting: str,
    path_lookup: Callable[[], str | None],
    managed: Callable[[], str | None],
) -> AdbLocation:
    """Resolution order, and why it's in this order:

    1. An explicit Settings override — the user said so, full stop.
    2. `adb` on **PATH** — what a dev machine expects, and today's behaviour.
    3. A copy zLog fetched itself (see ui/adb_fetcher.py).

    PATH beats the managed copy on purpose: a second adb at a different
    version will kill the running adb server of someone with Android Studio
    open ("adb server version doesn't match"). Never shadow an adb the user
    already has.
    """
    if setting:
        return setting, "setting"
    found = path_lookup()
    if found:
        return found, "path"
    managed_path = managed()
    if managed_path:
        return managed_path, "managed"
    return "adb", "none"


def managed_adb_path(app_data_dir: str) -> str:
    """Where a fetched adb would live under the app-data root, regardless of
    whether it's actually there yet (see ui/adb_fetcher.py's install step).

    Builds with the target platform's own path flavor (not whatever the host
    running this code happens to be) so the result — and this function's
    tests — don't depend on which OS is actually running it."""
    is_windows = sys.platform == "win32"
    pure_path = PureWindowsPath if is_windows else PurePosixPath
    exe = "adb.exe" if is_windows else "adb"
    return str(pure_path(app_data_dir) / "platform-tools" / exe)
