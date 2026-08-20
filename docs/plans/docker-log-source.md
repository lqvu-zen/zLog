# Plan: Docker container log source

- **Status:** Done  <!-- Draft | Approved | In progress | Done | Abandoned -->
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
| `src/zlog/core/containers.py` (new) | core | `parse_containers(output: str) -> list[Container]`, mirroring `core/devices.py::parse_devices` (same blank-line/malformed-line tolerance) against `docker ps --format PS_FORMAT` (`{{.ID}}\t{{.Names}}\t{{.Status}}`). Pure, unit-tested. |
| `src/zlog/ui/docker_dialog.py` (new) | ui | `DockerDialog` (pure view, like `LaunchDialog`) plus `list_containers()` — the one-shot `docker ps` subprocess call lives here rather than in a new `docker/` package, since it's a single ~10-line wrapper and there's no precedent elsewhere in this codebase for a package with one function; `core/containers.py` stays subprocess-free either way. |
| `src/zlog/ui/main_window.py` | ui | `attach_docker_container()`: no new reader class — constructs `LaunchReader(["docker", "logs", "-f", container.id])` directly, reusing `MainWindow._run_adb` (generic despite its name) for the FileNotFoundError/timeout → status-bar-message handling. `capture.attach(sess, reader, stream_label=f"docker:{name}")`. |
| `src/zlog/ui/menus.py` | ui | New File-menu action next to "&Launch App…". |
| `src/zlog/core/logformat.py` (built-in entry) | core | **Not implemented — deliberately deferred, not skipped by oversight.** Docker isn't installed in this build environment, and the Risks section below is explicit that the `--timestamps` format must be verified against a real install, not guessed. Shipping without `--timestamps` at all (see Risks) means there's nothing to parse yet; add the built-in format in a follow-up once someone can verify the real output shape. |
| `tests/test_containers.py`, `tests/test_docker_source.py` (new) | — | `parse_containers` cases; `DockerDialog` (pure view) selection/refresh; window wiring with a fake `LaunchReader` (same shape as `test_capture_controller.py`'s `StubReader`) so the suite runs without Docker installed. |

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
  sample line"). **Resolution for this pass:** `docker` isn't on PATH in this
  build environment (confirmed), so `--timestamps` was dropped entirely rather
  than guessed — `docker logs -f <id>` is plain, undecorated output, and
  `LaunchReader` stamps `time` with local capture time exactly as it already
  does for Launch App. The timestamp-parsing follow-up needs a real Docker
  install to verify against; tracked as an open question below, not silently
  dropped.

## Verification

- [x] `uv run pytest` — `tests/test_containers.py` (parse cases) and
      `tests/test_docker_source.py` (`DockerDialog` view behavior; window
      wiring: missing-docker error, successful attach with correct argv/
      stream_label, cancel starts nothing) — all green.
- [x] `uv run ruff check .` / `ruff format --check .` clean.
- [x] Manual (`run-zlog` `docker-attach` scenario, screenshotted): the picker
      renders two fake containers correctly, OK/Cancel gating works.
- [ ] Manual: run a real container that logs periodically, attach, confirm
      live streaming; `docker stop` the container and confirm `stream_ended`
      fires and the tab reflects it. **Not done — Docker isn't installed in
      this environment.** The window-wiring test above exercises the same
      code path with a fake reader (correct argv, stream_label, attach call),
      but a real end-to-end run against an actual container is still owed
      before calling this fully verified.
- [x] Manual: `docker` missing from PATH shows a clear error, not a dead
      picker — genuinely verified, since `docker` actually is missing from
      PATH in this environment (`test_attach_docker_container_missing_shows_error`
      exercises the real `list_containers()` → `FileNotFoundError` path, not a
      mock of that particular error).

## Open questions

- **Is `docker events`-based restart detection worth adding** as a follow-up?
  Defer until there's a concrete case where interleaved-lifetime logs actually
  confused someone.
- **Attach to existing (buffered) logs, then follow** — confirmed during
  implementation: `docker logs -f` (no other flags) already dumps existing
  output then follows, same as `FileFollower`'s default — no extra work
  needed, as recommended.
- **`--timestamps` + a built-in `LogFormat`** — deferred (see Risks). Needs a
  real Docker install to capture actual sample output before writing the
  pattern; revisit as its own small follow-up once that's available.
