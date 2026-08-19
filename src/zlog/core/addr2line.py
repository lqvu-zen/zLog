"""Pure command/output plumbing for `addr2line`/`llvm-addr2line` — no
subprocess execution here (that's `ui/native_symbolicator.py`, the one place
a native-symbolication subprocess actually runs, mirroring `core/parser.py`
staying pure while `adb/reader.py` does the actual `Popen`).
"""

from __future__ import annotations


def build_command(exe: str, so_path: str) -> list[str]:
    """`-f` prints the function name per address, `-C` demangles C++ names.
    No addresses on the command line — they're fed one per line on stdin, so
    one process handles a whole batch for one library."""
    return [exe, "-f", "-C", "-e", so_path]


def build_stdin(offsets: list[str]) -> str:
    return "\n".join(offsets) + "\n"


def parse_output(raw: str, offsets: list[str]) -> dict[str, str]:
    """`addr2line -f` prints two lines per input address (function name, then
    file:line) — pair them back up positionally with the input offsets, in
    the order they were sent. A malformed/short output leaves the trailing
    offsets unresolved rather than raising or misaligning the rest."""
    lines = raw.splitlines()
    result: dict[str, str] = {}
    for i, offset in enumerate(offsets):
        func_idx = i * 2
        if func_idx >= len(lines):
            break
        func = lines[func_idx].strip()
        if not func or func == "??":
            continue
        result[offset] = func
    return result
