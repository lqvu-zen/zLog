"""Device list parsing — pure, no Qt and no subprocess, so it's unit-testable."""

from __future__ import annotations

from dataclasses import dataclass

# Sources that aren't adb devices but share the picker + Start flow. The `local:`
# prefix is reserved: any serial carrying it is handled by a local reader, never
# passed to adb. Future local sources (event log, followed file) join by adding a
# sentinel here.
_LOCAL_PREFIX = "local:"
LOCAL_DBWIN = f"{_LOCAL_PREFIX}dbwin"  # Windows OutputDebugString capture

_LOCAL_LABELS = {LOCAL_DBWIN: "This PC (debug output)"}


def is_local_source(serial: str | None) -> bool:
    """True for a pseudo-device handled locally instead of through adb."""
    return bool(serial) and str(serial).startswith(_LOCAL_PREFIX)


@dataclass(frozen=True, slots=True)
class Device:
    """One entry from `adb devices`, or a local pseudo-source (see LOCAL_DBWIN)."""

    serial: str
    state: str  # "device" (ready), "offline", "unauthorized", ...

    @property
    def streamable(self) -> bool:
        """Only fully-online devices can be streamed from."""
        return self.state == "device"

    @property
    def is_local(self) -> bool:
        return is_local_source(self.serial)

    @property
    def label(self) -> str:
        """What to show in the picker."""
        if self.is_local:
            return _LOCAL_LABELS.get(self.serial, self.serial)
        return self.serial if self.streamable else f"{self.serial} ({self.state})"


def local_device() -> Device:
    """The 'This PC' entry for the picker (Windows debug output)."""
    return Device(serial=LOCAL_DBWIN, state="device")


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


def choose_device_index(
    devices: list[Device],
    preferred_serial: str | None,
    *,
    newly_connected=None,
) -> int:
    """Index of the source to preselect: a newly-connected real device (if any)
    wins outright, else the remembered serial if it's present and streamable,
    else the first streamable **real device**, else the first streamable entry
    at all (which may be the local 'This PC' source), else -1.

    Real devices win over the local source when nothing is remembered, so plugging
    in a phone still Just Works for the Android case; 'This PC' is only the default
    when it's the only thing available.

    `newly_connected` (optional): serials that just appeared since the previous
    refresh (see `DeviceController`). The **last** streamable, non-local device
    among them wins — plugging in a different device and hitting Refresh selects
    it without permanently forgetting the remembered one.
    """
    newly_connected = newly_connected or ()
    first_real = -1
    first_any = -1
    last_new = -1
    preferred_idx = -1
    for i, dev in enumerate(devices):
        if not dev.streamable:
            continue
        if first_any < 0:
            first_any = i
        if not dev.is_local:
            if first_real < 0:
                first_real = i
            if dev.serial in newly_connected:
                last_new = i
        if dev.serial == preferred_serial and preferred_idx < 0:
            preferred_idx = i
    if last_new >= 0:
        return last_new
    if preferred_idx >= 0:
        return preferred_idx
    return first_real if first_real >= 0 else first_any


def is_connect_ok(message: str) -> bool:
    """True if `adb connect`'s reply indicates success.

    adb's own wording: ``"connected to <addr>"`` / ``"already connected to
    <addr>"`` on success; anything else (``"failed to connect..."``,
    ``"cannot connect..."``, ``"unable to connect..."``, a timeout message)
    is a failure.
    """
    text = message.strip().lower()
    return text.startswith("connected to") or text.startswith("already connected to")


def is_serial_streamable(devices: list[Device], serial: str | None) -> bool:
    """True if we can (re)start a stream for `serial`. A falsy serial means the
    single default device, so any streamable device qualifies; otherwise the named
    serial must be present and online. Used by auto-reconnect to poll for return."""
    if not serial:
        return any(dev.streamable for dev in devices)
    return any(dev.serial == serial and dev.streamable for dev in devices)
