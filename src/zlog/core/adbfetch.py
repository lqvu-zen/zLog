"""Pure helpers for fetching platform-tools on demand (see
docs/plans/bundle-adb.md) — URL-building and integrity-checking need no
network or filesystem access, so they're unit-testable in isolation from the
download thread itself (ui/adb_fetcher.py).

The hash is pinned, not fetched at download time, and refreshed by hand during
releases (see the plan's "pin-and-refresh" decision) — a slightly stale adb is
fine, since a user's own adb (PATH or Settings) always wins over this fallback
(see core/adbpath.py). Never treat an unverified download as usable.
"""

from __future__ import annotations

import hashlib

# platform-tools 37.0.1, Windows — pinned at release time. Refresh both the
# hash and the revision comment when bumping (fetch the zip, sha256 it).
_WINDOWS_URL = "https://dl.google.com/android/repository/platform-tools-latest-windows.zip"
_WINDOWS_SHA256 = "45f4d63113e895ebde0c90f194099a4676b6ac653bd28d54314a9e022bbc1a99"
_WINDOWS_REVISION = "37.0.1"  # platform-tools/source.properties Pkg.Revision; humans only

_SOURCES: dict[str, tuple[str, str]] = {
    "win32": (_WINDOWS_URL, _WINDOWS_SHA256),
}


def platform_tools_url(os_name: str) -> str | None:
    """The pinned download URL for `os_name` (a `sys.platform` value), or None
    if fetching isn't offered there yet (macOS/Linux get a manual link
    instead — see the plan's scope)."""
    source = _SOURCES.get(os_name)
    return source[0] if source else None


def expected_sha256(os_name: str) -> str | None:
    """The pinned hash the download for `os_name` must match."""
    source = _SOURCES.get(os_name)
    return source[1] if source else None


def verify_download(data: bytes, expected_hash: str) -> bool:
    """True if `data` matches the pinned hash exactly."""
    return hashlib.sha256(data).hexdigest() == expected_hash
