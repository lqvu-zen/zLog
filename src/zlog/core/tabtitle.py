"""Building a tab's label — pure, so the rules are testable without a window.

A tab has to say three things in very little space: what it holds, what state
it's in, and how much is in it. Keeping the composition here (rather than inline
in `MainWindow._set_tab_label`) means the elision and precedence rules can be
unit-tested, and the window only has to decide which state applies.
"""

from __future__ import annotations

# Streaming already shipped as "●"; the rest follow the same visual language.
STREAMING = "streaming"
PAUSED = "paused"
DISCONNECTED = "disconnected"
IDLE = "idle"

_MARKERS = {
    STREAMING: "●",  # ● live
    PAUSED: "⏸",  # ⏸ capturing but not displaying
    DISCONNECTED: "⚠",  # ⚠ dropped, waiting to reconnect
    IDLE: "",
}

STATE_TEXT = {
    STREAMING: "streaming",
    PAUSED: "paused (buffering)",
    DISCONNECTED: "disconnected — waiting to reconnect",
    IDLE: "",
}

_MAX_LEN = 22


def format_count(n: int) -> str:
    """Compact line count: 999, 1.2k, 15k, 3.4M. Keeps the label narrow."""
    if n < 1000:
        return str(n)
    if n < 1_000_000:
        thousands = n / 1000
        return f"{thousands:.1f}k" if thousands < 10 else f"{thousands:.0f}k"
    millions = n / 1_000_000
    return f"{millions:.1f}M" if millions < 10 else f"{millions:.0f}M"


def tab_label(name: str, state: str = IDLE, count: int = 0, max_len: int = _MAX_LEN) -> str:
    """Compose ``<marker> <name> (<count>)``.

    Only the **name** is elided: the marker and count are the parts that stay
    useful when space is tight, so a long file name shrinks around them rather
    than pushing them out of view. A zero count is omitted entirely — a fresh tab
    shouldn't advertise "(0)".
    """
    marker = _MARKERS.get(state, "")
    suffix = f" ({format_count(count)})" if count > 0 else ""
    label = name or "Device"
    if len(label) > max_len:
        label = label[: max_len - 1] + "…"
    return f"{marker} {label}{suffix}".strip()


def tab_tooltip(name: str, state: str = IDLE, count: int = 0) -> str:
    """The full, unelided story for the tooltip — no truncation, state spelled out."""
    parts = [name or "Device"]
    if STATE_TEXT.get(state):
        parts.append(STATE_TEXT[state])
    if count > 0:
        parts.append(f"{count:,} line" + ("" if count == 1 else "s"))
    return " — ".join(parts)
