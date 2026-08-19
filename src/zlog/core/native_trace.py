"""Recognize native (NDK) crash backtrace frames and rewrite them once a
symbol's been resolved — pure, no Qt, no subprocess. Resolution itself
(core/addr2line.py, core/native_symbols.py, ui/native_symbolicator.py) is
elsewhere; this module only knows the text shape.

A tombstone/backtrace frame looks like:

    #00 pc 00012345  /data/app/~~xxx/base.apk!libnative.so (offset 0x3000)
    #01 pc 00001a2b  /system/lib64/libc.so (abort+164)

The second example is already symbolicated (has a `(name+offset)` suffix) —
nothing to resolve there. Only a frame with a bare `.so` and no trailing
symbol is a candidate.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_FRAME_RE = re.compile(
    r"^(\s*#\d+\s+pc\s+)([0-9a-fA-F]+)(\s+)(\S*?([\w.\-]+\.so))(\s*)(\(([^)]*)\))?(.*)$"
)


@dataclass(frozen=True, slots=True)
class NativeFrame:
    lib: str  # bare library file name, e.g. "libnative.so"
    offset: str  # hex offset, as captured (no "0x" prefix, matches `pc` field)


def parse_native_frame(message: str) -> NativeFrame | None:
    """A frame awaiting resolution, or `None` if the line isn't one, or is
    one that's already symbolicated (has a real `(name+off)` suffix rather
    than an `(offset 0x...)` placeholder)."""
    m = _FRAME_RE.match(message)
    if not m:
        return None
    offset, lib, paren_body = m.group(2), m.group(5), m.group(8)
    if paren_body and not paren_body.lower().startswith("offset"):
        return None  # already has a real symbol
    return NativeFrame(lib=lib, offset=offset)


def rewrite_native_frame(message: str, symbol: str) -> str:
    """Insert `symbol` into a frame line the same place `ndk-stack` does —
    appended after the library path, replacing an `(offset 0x...)`
    placeholder if the line had one."""
    m = _FRAME_RE.match(message)
    if not m:
        return message
    prefix, offset, gap1, lib_field, _lib, gap2, _paren, _body, rest = m.groups()
    return f"{prefix}{offset}{gap1}{lib_field} ({symbol}){rest}"
