"""Tests for the pure fetch helpers (URL/hash lookup, verification). No
network, no Qt — see ui/adb_fetcher.py for the actual download thread."""

import hashlib

from zlog.core.adbfetch import expected_sha256, platform_tools_url, verify_download


def test_windows_url_and_hash_are_pinned():
    assert platform_tools_url("win32").startswith("https://dl.google.com/")
    assert len(expected_sha256("win32")) == 64  # a sha256 hex digest


def test_unsupported_os_offers_no_fetch():
    assert platform_tools_url("linux") is None
    assert platform_tools_url("darwin") is None
    assert expected_sha256("linux") is None


def test_verify_download_accepts_matching_hash():
    data = b"pretend zip bytes"
    assert verify_download(data, hashlib.sha256(data).hexdigest())


def test_verify_download_rejects_tampered_or_truncated_data():
    data = b"pretend zip bytes"
    good_hash = hashlib.sha256(data).hexdigest()
    assert not verify_download(data + b"tampered", good_hash)
    assert not verify_download(data[:-1], good_hash)  # truncated
    assert not verify_download(b"", good_hash)
