"""Background resolution of native (NDK) crash-frame offsets against a
user-supplied symbols directory, via `addr2line`/`llvm-addr2line`.

Same signal discipline as every other reader (AdbReader, AdbFetcher): runs
entirely off the main thread and reaches the UI only via signals. A missing
tool, an unresolvable `.so`, or a subprocess failure resolves the affected
offsets to `None` (shown raw) rather than raising into the UI thread — see
docs/plans/crash-symbolication.md's "never guess" rule.
"""

from __future__ import annotations

import glob as glob_mod
import os
import subprocess

from PySide6.QtCore import QThread, Signal

from zlog.core.addr2line import build_command, build_stdin, parse_output
from zlog.core.applog import get_logger
from zlog.core.native_symbols import find_symbol_file

_log = get_logger()


def _glob_recursive(root: str, filename: str) -> list[str]:
    return glob_mod.glob(os.path.join(root, "**", filename), recursive=True)


class NativeSymbolResolver(QThread):
    # {(lib, offset): symbol_or_None} -- Signal(object), not Signal(dict):
    # PySide6's dict-to-QVariantMap conversion requires string keys, which
    # this tuple-keyed dict isn't.
    resolved = Signal(object)

    def __init__(
        self,
        pairs: list[tuple[str, str]],
        symbols_dir: str,
        addr2line_exe: str,
        device_abi: str | None,
        parent=None,
    ):
        super().__init__(parent)
        self._pairs = pairs
        self._symbols_dir = symbols_dir
        self._exe = addr2line_exe or "addr2line"
        self._abi = device_abi
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def run(self) -> None:
        results: dict[tuple[str, str], str | None] = {}
        by_lib: dict[str, list[str]] = {}
        for lib, offset in self._pairs:
            by_lib.setdefault(lib, []).append(offset)

        for lib, offsets in by_lib.items():
            if self._cancelled:
                return
            so_path = find_symbol_file(
                self._symbols_dir, lib, self._abi, os.path.isfile, _glob_recursive
            )
            if so_path is None:
                for offset in offsets:
                    results[(lib, offset)] = None
                continue
            resolved = self._resolve_one_library(so_path, offsets)
            for offset in offsets:
                results[(lib, offset)] = resolved.get(offset)

        if not self._cancelled:
            self.resolved.emit(results)

    def _resolve_one_library(self, so_path: str, offsets: list[str]) -> dict[str, str]:
        cmd = build_command(self._exe, so_path)
        try:
            proc = subprocess.run(
                cmd,
                input=build_stdin(offsets),
                capture_output=True,
                text=True,
                timeout=15,
            )
        except OSError as exc:
            _log.warning("addr2line failed for %s: %s", so_path, exc)
            return {}
        except subprocess.TimeoutExpired as exc:
            _log.warning("addr2line failed for %s: %s", so_path, exc)
            return {}
        return parse_output(proc.stdout, offsets)
