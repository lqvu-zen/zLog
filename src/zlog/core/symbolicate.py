"""The single call site every display/export path goes through to show a
deobfuscated/symbolicated message instead of the raw captured one — pure, no
Qt, no I/O. Doesn't mutate the raw text anywhere else; see
docs/plans/crash-symbolication.md ("Why filtering stays raw") for why this is
an on-demand overlay rather than baked into stored entries.
"""

from __future__ import annotations

from collections.abc import MutableMapping

from zlog.core.native_trace import parse_native_frame, rewrite_native_frame
from zlog.core.proguard import ProguardMapping, deobfuscate_line


class Symbolicator:
    """`mapping` (Java/Kotlin) and `native_cache` (native, `(lib, offset) ->
    symbol | None`) are read directly by the caller to update them in place —
    e.g. `symbolicator.native_cache.update(newly_resolved)` as resolutions
    land, or `symbolicator.mapping = parse_mapping(text)` on a fresh load.
    `enabled=False` is the "Symbolicate" toggle turned off: the loaded
    mapping/cache stay intact, `apply` just stops using them."""

    def __init__(self) -> None:
        self.mapping: ProguardMapping | None = None
        self.native_cache: MutableMapping[tuple[str, str], str | None] = {}
        self.enabled: bool = True

    def apply(self, message: str) -> str:
        if not self.enabled:
            return message
        frame = parse_native_frame(message)
        if frame is not None:
            symbol = self.native_cache.get((frame.lib, frame.offset))
            return rewrite_native_frame(message, symbol) if symbol else message
        if self.mapping is not None:
            return deobfuscate_line(self.mapping, message)
        return message
