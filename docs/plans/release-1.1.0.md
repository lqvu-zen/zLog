# Plan: Cut the 1.1.0 release

- **Status:** In progress  <!-- Draft | Approved | In progress | Done | Abandoned -->
- **Owner:** unassigned
- **Created:** 2026-07-31

## Goal

Ship zLog 1.1.0: a minor release covering everything landed since 1.0.0's
actual publish (2026-07-29) — the column header labels, auto-hiding
PID·TID/Tag segments, device-refresh improvements (prefer a newly-connected
device, retry an empty `adb devices` once), and persisting the last-launched
app across restarts.

## Steps

- [x] Confirm every plan intended for this release is Done (checked
      `docs/plans/README.md` for Draft/Approved/In progress — none pending).
- [x] Bump `__version__` (`src/zlog/__init__.py`) and `version`
      (`pyproject.toml`) to `1.1.0`.
- [x] Write `CHANGELOG.md` for 1.1.0 (only what's new since 1.0.0 — the App
      filter unification, Launch App button, etc. were already in 1.0.0's
      entry, not repeated here).
- [x] Release gate: `uv run pytest` (722 passed), `uv run ruff check .`,
      `uv run ruff format --check .` all green.
- [x] `uv lock` so the lockfile matches version 1.1.0.
- [x] Build the Windows exe locally and smoke-test it launches — log confirms
      "zLog 1.1.0 starting" with no errors.
- [ ] Commit everything, then tag and push:
      `git tag -a v1.1.0 -m "zLog 1.1.0"` and `git push --tags`.
- [ ] Watch `.github/workflows/release.yml` publish the GitHub Release
      automatically from the pushed tag.
- [ ] Replace the auto-generated release notes with the CHANGELOG section
      (same as 1.0.0 — GitHub's auto-notes are just a PR/commit list).

## Notes

- Versioning policy: this is the one time a bump is expected (releases only).
- After tagging, leave the version at 1.1.0 until the next release.
