# Plan: Docker container log source

- **Status:** Approved  <!-- Draft | Approved | In progress | Done | Abandoned -->
- **Owner:** unassigned
- **Created:** 2026-08-20
- **Related:** [windows-app-focus.md](windows-app-focus.md), [custom-log-format-editor.md](custom-log-format-editor.md)

## Goal

Attach to a running Docker container's log stream (`docker logs -f <container>`)
the same way `windows-app-focus.md` lets you attach to a launched app's console —
so a containerized service is debuggable in zLog without a separate terminal.

## Scope

- **In:** a container picker (via `docker ps`, parsed the same way
  `core/devices.py` parses `adb devices`); "Attach to Docker &Container…"
  File-menu action; capture via the **existing** `LaunchReader` (no new reader
  class — see Design) running `docker logs -f --timestamps <container>`.
- **Out (non-goals):** building/starting containers, docker-compose multi-service
  aggregation, remote Docker hosts (`DOCKER_HOST`) — local CLI/daemon only, same
  "must be on PATH" posture as `adb`; `docker events`-based restart detection
  (flagged as an open question, not required for v1).

## Design

| File | Layer | Change |
|---|---|---|
| `src/zlog/core/containers.py` (new) | core | `parse_containers(output: str) -> list[Container]`, mirroring `core/devices.py::parse_devices` exactly (same header/blank-line-skipping shape) against `docker ps --format "{{.ID}}\t{{.Names}}\t{{.Status}}"`. Pure, unit-tested. |
| `src/zlog/ui/docker_dialog.py` (new) | ui | Container list dialog; refresh runs `docker ps` off the UI thread (a one-shot subprocess call, not a persistent reader) and feeds `parse_containers`. |
| `src/zlog/ui/main_window.py` | ui | `attach_docker_container()` slot: no new reader class — constructs `LaunchReader(["docker", "logs", "-f", "--timestamps", container_id])` directly (`winlog/launcher.py` already does exactly what's needed: subprocess, line batching, `batch_ready`/`stream_ended` on the child process ending). `capture.attach(sess, reader, stream_label=f"docker:{name}")`. |
| `src/zlog/ui/menus.py` | ui | New File-menu action next to "&Launch App…". |
| `src/zlog/core/logformat.py` (built-in entry) | core | `docker logs --timestamps` prefixes every line with an RFC3339 stamp — worth one built-in `LogFormat` so `since:`/`until:` and the Time column work, using the machinery `custom-log-format-editor.md` already built for exactly this problem, rather than leaving the timestamp stuck in `message`. |
| `tests/test_containers.py` (new) | — | `parse_containers`: empty, several containers, various statuses, malformed line ignored. |

## Architecture touch points

- **Threading:** the `docker ps` refresh is a short one-shot subprocess call
  (mirror however `adb devices`/process-list refreshes already avoid blocking
  the UI thread); the actual capture reuses `LaunchReader`'s existing thread
  contract unchanged.
- **Model/proxy:** none.
- **Dependency direction:** `core/containers.py` Qt-free; the dialog and
  attach-flow are `ui`-only and reuse `winlog.launcher.LaunchReader` — note this
  is the one place a `ui` module reaches into `winlog`, which is already the
  established shape (`main_window.py` already imports `LaunchReader` today for
  the Windows launch flow) despite Docker itself being cross-platform; no new
  dependency-direction violation, just reusing an existing cross-platform class
  that happens to live in the `winlog` package.

## Risks & regressions to check

- **`docker` not on PATH, or the daemon not running** — must surface a clear
  error, not a silently-empty picker. This is the exact class of bug
  `usable-without-adb.md` fixed for a missing `adb`; don't reintroduce it here.
- **A container that exits mid-capture** is already covered for free —
  `LaunchReader.stream_ended` already fires when the child process (here,
  `docker logs -f`, not the container itself) exits on its own.
- **A restarting container** interleaves logs from separate lifetimes with no
  boundary marker from `docker logs -f` alone. A "container restarted" banner
  would need `docker events`, which is a bigger scope — flagged as an open
  question, not required for v1; don't silently pretend the boundary doesn't
  exist in the UI copy.
- **`--timestamps` format must be verified against a real Docker install**
  before committing to the built-in `LogFormat` pattern (exact separator/
  precision can vary by Docker version) — don't guess it from documentation
  alone (same lesson as `custom-log-format-preset.md`'s "don't guess from one
  sample line").

## Verification

- [ ] `uv run pytest` (`parse_containers` cases above)
- [ ] `uv run ruff check .` / `ruff format --check .`
- [ ] Manual: run a container that logs periodically, attach, confirm live
      streaming; `docker stop` the container and confirm `stream_ended` fires
      and the tab reflects it.
- [ ] Manual: `docker` missing from PATH shows a clear error, not a dead picker.

## Open questions

- **Is `docker events`-based restart detection worth adding** as a follow-up?
  Defer until there's a concrete case where interleaved-lifetime logs actually
  confused someone.
- **Attach to existing (buffered) logs, then follow** — i.e. `docker logs`
  without `-f` first, matching `FileFollower`'s `from_end=False` default of
  "read what's there, then follow"? Recommended: yes, `docker logs -f` already
  does this by default (dumps existing output, then follows), so no extra work
  needed — confirm during implementation rather than assuming.
