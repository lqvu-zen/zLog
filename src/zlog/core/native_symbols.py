"""Find the unstripped `.so` matching a library name — pure logic, all
filesystem access injected as callables (same testability pattern as
`core/adbpath.py`'s `path_lookup`/`managed`), so it unit-tests with a fake
filesystem, no real disk needed.

Resolution order (see docs/plans/crash-symbolication.md) — deliberately
stops rather than guesses past this list, since a wrong `.so` produces a
wrong-but-confident symbol, which is worse than an unresolved frame:

1. `<symbols_dir>/<lib>` (flat).
2. `<symbols_dir>/<device_abi>/<lib>`, if a device ABI is known.
3. Exactly one match for `**/<lib>` under `symbols_dir` (recursive) — used
   only when unambiguous.
4. Otherwise: unresolved (`None`).
"""

from __future__ import annotations

from collections.abc import Callable


def find_symbol_file(
    symbols_dir: str,
    lib: str,
    device_abi: str | None,
    exists: Callable[[str], bool],
    glob_recursive: Callable[[str, str], list[str]],
) -> str | None:
    """`exists(path) -> bool` and `glob_recursive(root, filename) -> [paths]`
    are injected so this needs no real filesystem to test."""
    if not symbols_dir:
        return None

    flat = _join(symbols_dir, lib)
    if exists(flat):
        return flat

    if device_abi:
        by_abi = _join(_join(symbols_dir, device_abi), lib)
        if exists(by_abi):
            return by_abi

    matches = glob_recursive(symbols_dir, lib)
    if len(matches) == 1:
        return matches[0]

    return None


def _join(a: str, b: str) -> str:
    a = a.rstrip("/\\")
    return f"{a}/{b}"
