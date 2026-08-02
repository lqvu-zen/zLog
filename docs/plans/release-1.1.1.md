# Plan: Cut the 1.1.1 release

- **Status:** Done  <!-- Draft | Approved | In progress | Done | Abandoned -->
- **Owner:** unassigned
- **Created:** 2026-08-01
- **Related:** [release-workflow.md](release-workflow.md), [release-1.1.0.md](release-1.1.0.md), [usable-without-adb.md](usable-without-adb.md), [bundle-adb.md](bundle-adb.md)

## Goal

Ship the commits sitting on `main` since `v1.1.0` — most importantly the fix
for a bug that makes the Windows flow **unreachable** in the build users have.

## Why — a shipped bug is sitting fixed but unreleased

`3c476ee` ("Keep zLog usable without adb") fixes a defect *present in 1.1.0*:
`refresh_devices()` returned early when adb was missing, so the device picker
never got its **This PC** entry and Start stayed disabled. A Windows user with no
Android tooling — the exact audience the Windows capture features were built for —
downloads 1.1.0 and finds the primary path dead.

That fix has been on `main` since 2026-07-30 and is in nobody's hands.

**Updated 2026-08-02:** this plan originally scoped ~10 commits; the tech-debt
program (`ci-windows-job.md`, `gitattributes-line-endings.md`,
`architecture-doc-refresh.md`, `main-window-drift.md`) landed on `main` in the
meantime rather than waiting, per that program's own open question ("should
tech-debt land first? ... exception: if it's going to land this week anyway").
None of it changes user-facing behavior, so the release calculus is unchanged —
still a patch — but the commit list below is the real one, not the original
estimate.

| Commit(s) | Change | User-facing? |
|---|---|---|
| `3c476ee` | **Fix:** This PC stays reachable without adb (the shipped bug) | Yes |
| `e8e6578`, `53c3808` | Offer to fetch adb, scoped to Android intent | Yes |
| `0180ff7` | README: how to get adb | Docs only |
| `c291055` | UI fixes: Settings adb-path clipping, noisy cold-start status | Yes |
| `82d54f8` | UI fix: device-bar min-width trimmed; "This PC" tab shows a name, not `local:dbwin` | Yes |
| `ab884e0` | Retitle to "Live Log Viewer" | Yes |
| `f8e94e1`, `ca094e7`, `84c9ff5` | CI-failure fixes (test determinism; a real 5-reader `_running` race caught by the new Windows job) | No — but `84c9ff5` fixed a real latent bug in `AdbReader`/`DebugOutputReader`/`EventLogReader`/`LaunchReader`/`FileLoader` (see below) |
| `1f9ef25`, `319de5d` | `.gitattributes` + line-ending renormalize | No |
| `61a8919` | Windows CI job added (caught the two bugs above on its first two runs) | No |
| `b8d9c8f` | ARCHITECTURE/ROADMAP/README doc refresh | No |
| `52d7931` | `main_window.py` drift fix: convention + `export_actions.py`/`adb_setup_flow.py` extractions | No (pure move, verified) |
| `86a1121`, `bdb37ad`, `208a40f`, `a59cd3a`, `308268d`, `8be3353`, `bfa5106` | plan/docs only | No |

The one **user-facing** addition beyond the original scope: the `_running`
race fix (`84c9ff5`) is a real correctness fix, not just a CI-hygiene item — a
reader thread that got `stop()`'d in the narrow window before its `run()`
finished setup could keep running forever undetected. Worth a CHANGELOG
mention alongside the adb fix, phrased for what a user could have hit (a
capture that wouldn't actually stop).

This is still a **patch** release by semver: bug fixes plus additive,
non-breaking improvements to an existing area, plus internal-only work with
zero surface change. No API or file-format change.

## Scope

- **In:** version bump to `1.1.1` in both places, CHANGELOG entry, tag, Windows
  build via `release.yml`, release notes led by the adb fix.
- **Out (non-goals):** new features; any 1.2.0 scope; a CHANGELOG entry for the
  internal-only commits (CI, docs, refactor) — Keep a Changelog convention here
  is user-facing changes only, matching 1.1.0's own section headers.

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

- [x] Both version strings read `1.1.1` (`src/zlog/__init__.py`, `pyproject.toml`);
      `uv lock` refreshed to match.
- [x] Windows build succeeds (`cx_Freeze`); `zlog.exe` launches and stays up —
      verified by starting it, confirming the process is alive with a normal
      memory footprint a few seconds in, then stopping it cleanly.
- [x] Tag pushed, release notes published (via `release.yml` off the `v1.1.1` tag).
- [ ] `uv run pytest -q` in one process, `uv run ruff check .` / `format --check .`
      — **not re-run as a release gate for this cut.** By this point every
      commit going into 1.1.1 had already gone through its own CI run on
      `main` (including the two Windows-job runs still finishing as this
      release started); the user asked to skip re-verification and ship. Real
      full-suite/shuffled-suite runs earlier in this session (see
      [ci-shuffled-order.md](ci-shuffled-order.md)) were green.
- [ ] **Manual, adb removed from PATH:** This PC listed, enabled, Start works —
      **not independently re-verified against this exact artifact.** The fix
      itself (`3c476ee`) has its own plan/tests; skipped here per the same
      instruction.
- [ ] Manual with a device attached: Android streaming — same, not re-verified
      against this artifact for this release.

## Open questions

- **Should the tech-debt plans land first?** No — none of them changes behaviour,
  and the fix shouldn't wait. Exception: if
  [gitattributes-line-endings.md](gitattributes-line-endings.md) is going to
  land this week anyway, doing it *before* the tag keeps the renormalize commit
  out of the release diff.
- Is 1.1.1 right, or does the retitle argue for 1.2.0? Leaning 1.1.1: a window
  title and README change isn't a feature.
