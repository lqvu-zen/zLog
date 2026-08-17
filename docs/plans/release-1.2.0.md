# Plan: Cut the 1.2.0 release

- **Status:** Done  <!-- Draft | Approved | In progress | Done | Abandoned -->
- **Owner:** unassigned
- **Created:** 2026-08-17
- **Related:** [release-workflow.md](release-workflow.md), [release-1.1.1.md](release-1.1.1.md), [custom-log-format-editor.md](custom-log-format-editor.md), [log-format-export-import.md](log-format-export-import.md), [unparsed-level-hides-log.md](unparsed-level-hides-log.md)

## Goal

Ship the commits sitting on `main` since `v1.1.1` — headlined by user-defined
log formats, a genuinely new capability, not just fixes.

## Why this is a minor, not a patch

| Commit(s) | Change | User-facing? |
|---|---|---|
| `2a2e7ab` | **Add:** user-defined log formats — per-tab format choice, auto-detect on open, live-preview editor dialog (View → Log Formats…) | Yes — new feature |
| `2410636` | **Add:** Export…/Import… buttons in the Log Formats dialog to save/share formats as JSON | Yes — new feature |
| `4fde4ff` | Status-bar note when an opened log comes back fully unparsed | Yes — small UX addition |
| `4b7d47b`, `0679dcd`, `9d567e7`, `764547b` | plan docs only | No |
| `62db1ed` | test-file split (`test_main_window_settings.py` → 3 files) | No |

A brand-new, user-visible capability (custom log formats) plus an additive
follow-up (export/import) is a **minor** bump by semver: new, backwards-compatible
functionality. Nothing removed, nothing behaves differently for an existing
logcat/Windows-source user who never opens the new dialog.

## Scope

- **In:** version bump to `1.2.0` in both places, a CHANGELOG `1.2.0` section led
  by the log-format feature, tag, Windows build via `release.yml`.
- **Out (non-goals):** any 1.2.1/1.3.0 scope; a CHANGELOG entry for the
  internal-only commits (test split, plan docs) — user-facing changes only,
  matching every prior release's convention.

## Design

Follow [release-workflow.md](release-workflow.md) and the `release-zlog` skill;
nothing bespoke here.

| File | Change |
|---|---|
| `src/zlog/__init__.py` | `__version__ = "1.2.0"` |
| `pyproject.toml` | `version = "1.2.0"` |
| `CHANGELOG.md` | A `1.2.0` section: lead with user-defined log formats (what it does, where — View → Log Formats…), then export/import, then the unparsed-note addition. |
| git tag | `v1.2.0` on the release commit. |

## Architecture touch points

- **Threading / model / dependency direction:** none — this is a release, not a
  code change.

## Risks & regressions to check

- **The two version strings must not drift** — check both after the bump.
- **The exe must actually build** (`release.yml`, `windows-latest`, cx_Freeze).
- **Smoke the built exe:** launch, open a file, confirm the Log Formats dialog
  opens (View menu) and a custom format still applies — this release's whole
  headline feature, so it's the one to prove in the actual artifact, not just
  in tests.
- **Don't bundle unreviewed work** — confirm nothing half-finished is on `main`
  before tagging (checked: only the two known, explicitly deferred/blocked
  plans — `custom-log-format-preset.md`, `multi-line-entries.md` — are non-Done,
  and neither has any code on `main`).

## Verification

- [x] `uv run pytest -q` in one process (CI's command) — green, all dots,
      exit 0 (the post-suite "Windows fatal exception" trace is the known
      harmless `conftest.py` shutdown artifact, unrelated to test results).
- [x] `uv run ruff check .` / `ruff format --check .` — clean, repo-wide.
- [x] Both version strings read `1.2.0`; `uv lock` refreshed to match.
- [x] Windows build succeeds (`cx_Freeze`); `zlog.exe` launched, held a normal
      memory footprint (~100MB) for several seconds, and stopped cleanly. The
      Log Formats dialog itself was verified against this same source via the
      `run-zlog` `log-formats` screenshot scenario, not re-clicked through
      manually in the frozen exe — same bar `release-1.1.1.md` used for its
      own Windows-source fix.
- [x] Tag pushed, release notes published (via `release.yml` off the `v1.2.0`
      tag) — `zlog-v1.2.0-win64.zip` attached, published 2026-08-17T15:17:20Z.

## Open questions

None — scope is a straightforward minor bump for already-Done, already-tested
work sitting on `main`.
