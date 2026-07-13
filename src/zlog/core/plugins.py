"""Load user *colorizer* plugins from a directory.

A plugin is a `.py` file that may define `colorize(entry) -> str | None`, returning
a hex color for a row (or None to skip). Loading executes the file, so plugins are
trusted user code; a broken plugin is skipped without breaking the others.
"""

from __future__ import annotations

import os
from collections.abc import Callable


def load_colorizers(directory: str) -> tuple[list[Callable], list[str]]:
    """Return (colorizers, errors) discovered in `directory` (sorted by filename)."""
    colorizers: list[Callable] = []
    errors: list[str] = []
    if not directory or not os.path.isdir(directory):
        return colorizers, errors
    for name in sorted(os.listdir(directory)):
        if not name.endswith(".py") or name.startswith("_"):
            continue
        path = os.path.join(directory, name)
        try:
            with open(path, encoding="utf-8") as fh:
                code = fh.read()
            namespace: dict = {}
            exec(compile(code, path, "exec"), namespace)  # noqa: S102 (trusted plugin)
            fn = namespace.get("colorize")
            if callable(fn):
                colorizers.append(fn)
        except Exception as exc:  # a bad plugin must not break the rest
            errors.append(f"{name}: {exc}")
    return colorizers, errors


def apply_colorizers(colorizers, entry) -> str | None:
    """First non-None color from the colorizers; a raising colorizer is skipped."""
    for fn in colorizers:
        try:
            color = fn(entry)
        except Exception:
            continue
        if color:
            return color
    return None
