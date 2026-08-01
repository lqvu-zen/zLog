# Plan: Cut the 1.1.1 release

- **Status:** Draft  <!-- Draft | Approved | In progress | Done | Abandoned -->
- **Owner:** unassigned
- **Created:** 2026-08-01
- **Related:** [release-workflow.md](release-workflow.md), [release-1.1.0.md](release-1.1.0.md), [usable-without-adb.md](usable-without-adb.md), [bundle-adb.md](bundle-adb.md)

## Goal

Ship the ten commits sitting on `main` since `v1.1.0` — most importantly the fix
for a bug that makes the Windows flow **unreachable** in the build users have.

## Why — a shipped bug is sitting fixed but unreleased

`3c476ee` ("Keep zLog usable without adb") fixes a defect *present in 1.1.0*:
`refresh_devices()` returned early when adb was missing, so the device picker
never got its **This PC** entry and Start stayed disabled. A Windows user with no
Android tooling — the exact audience the Windows capture features were built for —
downloads 1.1.0 and finds the primary path dead.

That fix has been on `main` since 2026-07-30 and is in nobody's hands. Everything
else in the window is user-visible improvement on top:

| Commit | Change |
|---|---|
| `3c476ee` | **Fix:** This PC stays reachable without adb (the shipped bug) |
| `e8e6578`, `53c3808` | Offer to fetch adb, scoped to Android intent |
| `0180ff7` | README: how to get adb |
| `c291055` | UI fixes: Settings adb-path clipping, noisy cold-start status |
| `ab884e0` | Retitle to "Live Log Viewer" |
| `f8e94e1` | CI fix (adb-setup-prompt tests) |
| `308268d`, `8be3353`, `bfa5106` | plan/docs only |

This is a **patch** release by semver: one bug fix plus additive, non-breaking
improvements to an existing area. No API or file-format change.

## Scope

- **In:** version bump to `1.1.1` in both places, CHANGELOG entry, tag, Windows
  build via `release.yml`, release notes led by the adb fix.
- **Out (non-goals):** waiting for any tech-debt work to land — none of it is
  user-visible and the fix shouldn't wait for it; new features; and any 1.2.0
  scope.

## Design

Follow [release-workflow.md](release-workflow.md) and the `release-zlog` skill;
nothing bespoke here. Version lives in two files and both must move together:

| File | Change |
|---|---|
| `src/zlog/__init__.py` | `__version__ = "1.1.1"` |
| `pyproject.toml` | `version = "1.1.1"` |
| `CHANGELOG.md` | A `1.1.1` section. **Lead with the fix**, phrased for the affected user ("zLog no longer requires adb to use the Windows sources"), then the adb-fetch offer, then the retitle. |
| git tag | `v1.1.1` on the release commit. |

Per `CLAUDE.md`, this is the **only** kind of change that may bump the version.

## Architecture touch points

- **Threading / model / dependency direction:** none.

## Risks & regressions to check

- **The two version strings must not drift.** They've been kept in sync by hand;
  check both after the bump.
- **The exe must actually build** — `release.yml` is `windows-latest` and is the
  only Windows CI we have today (see [ci-windows-job.md](ci-windows-job.md)); a
  build failure here is discovered late by definition.
- **Smoke the built exe on Windows**, don't just trust a green build: launch,
  pick **This PC**, Start, confirm lines arrive. That's the exact path 1.1.0
  broke, so it's the one to prove.
- **Verify the fix in the artifact, not the repo:** on a machine (or a shell) with
  adb genuinely off `PATH`, the shipped exe must list This PC and enable Start.
- **Release notes shouldn't bury the fix** under the retitle. The rename is the
  most *visible* change and the least *important* one.
- **Don't bundle unreviewed work**: confirm nothing half-finished is on `main`
  before tagging.

## Verification

- [ ] `uv run pytest -q` in **one process** (CI's command) — green. Local chunked
      runs don't count as the gate for a release.
- [ ] `uv run ruff check .` and `uv run ruff format --check .` clean.
- [ ] Both version strings read `1.1.1`; `zlog --version` (or About) agrees.
- [ ] Windows build succeeds; `zlog.exe` launches.
- [ ] **Manual, adb removed from PATH:** This PC listed, enabled, Start works —
      the 1.1.0 bug is gone in the artifact.
- [ ] Manual with a device attached: Android streaming still works (no regression
      from the adb-resolution change).
- [ ] Tag pushed, release notes published.

## Open questions

- **Should the tech-debt plans land first?** No — none of them changes behaviour,
  and the fix shouldn't wait. Exception: if
  [gitattributes-line-endings.md](gitattributes-line-endings.md) is going to
  land this week anyway, doing it *before* the tag keeps the renormalize commit
  out of the release diff.
- Is 1.1.1 right, or does the retitle argue for 1.2.0? Leaning 1.1.1: a window
  title and README change isn't a feature.
