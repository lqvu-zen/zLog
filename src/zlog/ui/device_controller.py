"""Device picker + package/PID filter state, extracted from MainWindow.

Holds no widgets, so the selection preference, the package filter, and live
PID-tracking can be unit-tested without constructing a MainWindow (or even a
QApplication — a bare QObject needs neither). The window drives its widgets and
the proxy from this controller's state and return values.
"""

from __future__ import annotations

from PySide6.QtCore import QObject

from zlog.core.devices import Device, choose_device_index
from zlog.core.proc import parse_proc_start


class DeviceController(QObject):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.devices: list[Device] = []
        self.preferred_serial: str | None = None  # last-used device, restored on launch
        self.filter_package: str | None = None
        self.filter_pids: set[str] = set()
        # Real (non-local) serials seen streamable as of the *previous* refresh.
        # None until the first refresh, so app startup never treats everything as
        # "newly connected" — that would silently defeat remember-device.md.
        self._known_real_serials: set[str] | None = None
        self._newly_connected: frozenset[str] = frozenset()

    # --- device selection --------------------------------------------------
    def set_devices(self, devices) -> None:
        self.devices = list(devices)
        current = {d.serial for d in self.devices if d.streamable and not d.is_local}
        if self._known_real_serials is None:
            self._newly_connected = frozenset()  # first-ever refresh: no baseline yet
        else:
            # Tracks *streamable* serials specifically (not just "seen"), so a
            # device that was unauthorized on the last refresh and just got
            # allowed still counts as newly connected now that it's usable.
            self._newly_connected = frozenset(current - self._known_real_serials)
        self._known_real_serials = current

    def choose_index(self) -> int:
        """Which device index the picker should select for the current list."""
        return choose_device_index(
            self.devices, self.preferred_serial, newly_connected=self._newly_connected
        )

    def remember(self, serial: str | None) -> None:
        """Record a real (streamable) selection so it's reselected next time; a
        None selection (the 'No devices' placeholder) must not wipe the memory."""
        if serial is not None:
            self.preferred_serial = serial

    # --- package / PID filter ----------------------------------------------
    @property
    def filtering(self) -> bool:
        return self.filter_package is not None

    def apply_filter(self, package: str, pids) -> None:
        self.filter_package = package
        self.filter_pids = set(pids)

    def clear_filter(self) -> None:
        self.filter_package = None
        self.filter_pids = set()

    def track(self, entries) -> list[str]:
        """Add PIDs of newly-started processes of the filtered package (so the
        filter survives a restart). Returns the newly-added PIDs (sorted), or []
        when there's no filter or nothing new."""
        if self.filter_package is None:
            return []
        added: list[str] = []
        for entry in entries:
            result = parse_proc_start(entry.message)
            if result is None:
                continue
            pid, package = result
            if package == self.filter_package and pid not in self.filter_pids:
                self.filter_pids.add(pid)
                added.append(pid)
        return sorted(added)
