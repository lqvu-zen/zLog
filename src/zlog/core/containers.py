"""Docker container list parsing — pure, no Qt and no subprocess, so it's
unit-testable (see docs/plans/docker-log-source.md)."""

from __future__ import annotations

from dataclasses import dataclass

# Passed to `docker ps` so parse_containers gets one predictable tab-separated
# shape regardless of the local Docker CLI's default table formatting/locale.
PS_FORMAT = "{{.ID}}\t{{.Names}}\t{{.Status}}"


@dataclass(frozen=True, slots=True)
class Container:
    """One row of `docker ps` output."""

    id: str
    name: str
    status: str


def parse_containers(output: str) -> list[Container]:
    """Parse `docker ps --format` output built from `PS_FORMAT` above.

    One container per line, tab-separated; blank lines and a line with fewer
    than 3 fields are skipped rather than raising, mirroring
    `core/devices.py::parse_devices`'s tolerance of odd output.
    """
    containers = []
    for raw in output.splitlines():
        if not raw.strip():
            continue
        parts = raw.split("\t")
        if len(parts) < 3:
            continue
        containers.append(Container(id=parts[0], name=parts[1], status=parts[2]))
    return containers
