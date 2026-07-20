"""Row-density presets — pure config, no Qt, so it's unit-testable.

The delegate/window turn a preset name into the per-row vertical padding (in
pixels, added on top of the font height). Keeping the mapping here means no
widget hard-codes the numbers. See docs/plans/density-modes.md.
"""

from __future__ import annotations

# Extra vertical pixels per row, on top of the font height. "default" matches
# the historical row spacing (the old literal `+ 4`).
DENSITY_PAD = {
    "compact": 2,
    "default": 4,
    "comfortable": 10,
}

DEFAULT_DENSITY = "default"

# Order shown in the Settings dropdown (loosest reading order: tight → roomy).
DENSITY_NAMES = ("compact", "default", "comfortable")


def density_pad(name: str) -> int:
    """Vertical row padding (px) for a density preset; unknown names fall back
    to the default so a stale setting can't produce a zero-height row."""
    return DENSITY_PAD.get(name, DENSITY_PAD[DEFAULT_DENSITY])
