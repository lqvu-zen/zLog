"""Curated default Event Log channel list (see docs/plans/windows-event-log.md).

Plain data — the channel picker lets you type any other channel name too
(via `wevtutil el` on Windows, or from memory), so this is a starting point,
not an exhaustive enumeration.
"""

from __future__ import annotations

DEFAULT_CHANNELS = ["Application", "System", "Setup", "Security"]
