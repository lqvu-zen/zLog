"""Device list parsing — pure, no Qt and no subprocess, so it's unit-testable."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Device:
    """One entry from `adb devices`."""

    serial: str
    state: str  # "device" (ready), "offline", "unauthorized", ...

    @property
    def streamable(self) -> bool:
        """Only fully-online devices can be streamed from."""
        return self.state == "device"

    @property
    def label(self) -> str:
        """What to show in the picker."""
        return self.serial if self.streamable else f"{self.serial} ({self.state})"


def parse_devices(output: str) -> list[Device]:
    """Parse the text output of `adb devices`.

    Example input::

        List of devices attached
        emulator-5554   device
        ABCD1234        unauthorized

    Header, blank lines, and daemon-noise lines (starting with '*') are ignored.
    """
    devices: list[Device] = []
    for raw in output.splitlines():
        line = raw.strip()
        if not line or line.startswith("List of devices") or line.startswith("*"):
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        devices.append(Device(serial=parts[0], state=parts[1]))
    return devices


def choose_device_index(devices: list[Device], preferred_serial: str | None) -> int:
    """Index of the device to preselect: the remembered serial if it's present and
    streamable, else the first streamable device, else -1 (nothing selectable)."""
    first = -1
    for i, dev in enumerate(devices):
        if dev.streamable:
            if first < 0:
                first = i
            if dev.serial == preferred_serial:
                return i
    return first
