# Plan: Cut the 1.3.0 release

- **Status:** Done  <!-- Draft | Approved | In progress | Done | Abandoned -->
- **Owner:** unassigned
- **Created:** 2026-08-17
- **Related:** [release-workflow.md](release-workflow.md), [release-1.2.0.md](release-1.2.0.md), [app-icon.md](app-icon.md), [use-downloaded-adb.md](use-downloaded-adb.md)

## Goal

Ship the commits sitting on `main` since `v1.2.0` — a real app icon and an
explicit way to use zLog's own downloaded adb copy.

## Why this is a minor, not a patch

| Commit(s) | Change | User-facing? |
|---|---|---|
| `31fb44c` | **Add:** a real app icon (window, taskbar, and the built `.exe`'s file icon) — zLog previously used Qt's generic default everywhere | Yes — new, additive |
| `b64930d` | **Add:** "Use downloaded copy" button in Settings' adb-path row, to explicitly prefer zLog's already-fetched adb over a different one on PATH | Yes — new, additive |
| `0806dc2` | plan doc only (closing out `release-1.2.0.md`'s own verification note) | No |

Both changes are additive and backwards-compatible — nothing removed, nothing
behaves differently for a user who never opens Settings or never noticed the
old default icon. A **minor** bump by semver.

## Scope

- **In:** version bump to `1.3.0` in both places, a CHANGELOG `1.3.0` section,
  tag, Windows build via `release.yml`.
- **Out (non-goals):** any 1.3.1/1.4.0 scope; a CHANGELOG entry for the
  internal-only commit.

## Design

Follow [release-workflow.md](release-workflow.md) and the `release-zlog` skill.

| File | Change |
|---|---|
| `src/zlog/__init__.py` | `__version__ = "1.3.0"` |
| `pyproject.toml` | `version = "1.3.0"` |
| `CHANGELOG.md` | A `1.3.0` section: the app icon first (most visible), then the adb Settings button. |
| git tag | `v1.3.0` on the release commit. |

## Architecture touch points

- **Threading / model / dependency direction:** none — a release, not a code
  change.

## Risks & regressions to check

- **The two version strings must not drift.**
- **The exe must actually build**, and this release specifically needs its
  **file icon** checked in the artifact (the whole point of `app-icon.md`) —
  already verified once during that plan's own work, but worth reconfirming
  against the exact build this tag produces.
- **Don't bundle unreviewed work** — confirmed only the two known,
  already-reported non-Done plans (`custom-log-format-preset.md`, blocked;
  `multi-line-entries.md`, deferred) are outstanding, and neither has any code
  on `main`.

## Verification

- [x] CI green on `b64930d` (the last commit before this release that
      touches `src/`/`tests/`/`pyproject.toml`/`uv.lock` — the adb Settings
      button): `completed`/`success`, confirmed via `gh run list`. Per the
      `release-zlog` skill change made mid-cut (see
      `.claude/skills/release-zlog/SKILL.md`), this replaces a local
      `pytest`/`ruff` run as the gate. The local full-suite run attempted
      earlier in this same cut hit the 10-minute foreground timeout,
      backgrounded, then failed with an unexplained exit code 4 partway
      through (no traceback, no FAILED lines); rather than chase that, the
      gate itself changed to check CI instead.
- [x] Both version strings read `1.3.0`; `uv lock` refreshed to match.
- [x] Windows build succeeds (`cx_Freeze`); `zlog.exe` shows the new icon as
      its file icon and launches with it as the window/taskbar icon —
      confirmed against this exact build (`MainWindowTitle=zLog - Live Log
      Viewer`, exe icon 32x32 via `System.Drawing.Icon`), then stopped
      cleanly.
- [ ] Tag pushed, release notes published (via `release.yml` off the `v1.3.0` tag).

## Open questions

None.
