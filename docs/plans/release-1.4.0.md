# Plan: Cut the 1.4.0 release

- **Status:** Done  <!-- Draft | Approved | In progress | Done | Abandoned -->
- **Owner:** unassigned
- **Created:** 2026-08-19
- **Related:** [release-workflow.md](release-workflow.md), [release-1.3.0.md](release-1.3.0.md), [crash-symbolication.md](crash-symbolication.md)

## Goal

Ship crash symbolication — the commit sitting on `main` since `v1.3.0`.

## Why this is a minor, not a patch

| Commit(s) | Change | User-facing? |
|---|---|---|
| `64f1541` | **Add:** deobfuscate Java/Kotlin (ProGuard/R8 `mapping.txt`) and symbolicate native/NDK (`addr2line`) crash traces, via a new Symbol bar under the device bar | Yes — new, additive |
| `7b20cc4` | plan doc only (closing out `release-1.3.0.md`'s own verification note) | No |

A large, additive new capability, nothing removed or changed for anyone who
never touches the new bar. A **minor** bump by semver.

## Scope

- **In:** version bump to `1.4.0` in both places, a CHANGELOG `1.4.0` section,
  tag, Windows build via `release.yml`.
- **Out (non-goals):** any 1.4.1/1.5.0 scope; a CHANGELOG entry for the
  internal-only commit.

## Design

Follow [release-workflow.md](release-workflow.md) and the `release-zlog` skill.

| File | Change |
|---|---|
| `src/zlog/__init__.py` | `__version__ = "1.4.0"` |
| `pyproject.toml` | `version = "1.4.0"` |
| `CHANGELOG.md` | A `1.4.0` section describing the Symbol bar / deobfuscation / symbolication feature. |
| git tag | `v1.4.0` on the release commit. |

## Architecture touch points

- **Threading / model / dependency direction:** none — a release, not a code
  change.

## Risks & regressions to check

- **The two version strings must not drift.**
- **The exe must actually build**, with the new Symbol bar UI present (build
  succeeded, real window confirmed via the running exe; the bar's actual
  behavior was already verified end-to-end during `crash-symbolication.md`'s
  own work — same source, now frozen into this build).
- **Don't bundle unreviewed work** — confirmed only the two known,
  already-reported non-Done plans (`custom-log-format-preset.md`, blocked;
  `multi-line-entries.md`, deferred) are outstanding, and neither has any code
  on `main`.

## Verification

- [x] CI green on `64f1541` (the last commit before this release that touches
      `src/`/`tests/`/`pyproject.toml`/`uv.lock` — the crash-symbolication
      feature): `completed`/`success`, confirmed via `gh run list` before
      starting this release.
- [x] Both version strings read `1.4.0`; `uv lock` refreshed to match.
- [x] Windows build succeeds (`cx_Freeze`); `zlog.exe` launched, a real
      top-level window came up (`MainWindowTitle=zLog - Live Log Viewer`),
      then stopped cleanly.
- [ ] Tag pushed, release notes published (via `release.yml` off the `v1.4.0` tag).

## Open questions

None.
