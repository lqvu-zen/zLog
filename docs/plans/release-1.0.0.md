# Plan: Cut the 1.0.0 release

- **Status:** Done  <!-- Draft | Approved | In progress | Done | Abandoned -->
- **Owner:** Vũ
- **Created:** 2026-07-01

## Goal

Ship zLog 1.0.0: the first stable, tagged release with a Windows executable.

## Steps

- [x] Bump `__version__` (`src/zlog/__init__.py`) and `version` (`pyproject.toml`) to `1.0.0`.
- [x] Write `CHANGELOG.md` for 1.0.0.
- [x] Release gate: `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .` all green.
- [x] (your machine) `uv lock` so the lockfile matches Python 3.14 + version 1.0.0.
- [x] (your machine) Commit everything, then tag and push:
      `git tag -a v1.0.0 -m "zLog 1.0.0"` and `git push --tags`.
- [x] (your machine) Build the Windows exe (see below) and attach it to the GitHub release.
- [x] (your machine) Create the GitHub Release for `v1.0.0` using the notes below.

## Windows build (cx_Freeze)

```powershell
uv run --extra build python cxfreeze_setup.py build
# → build\exe.win-amd64-<pyver>\zlog.exe   (or double-click build.bat)
```

See the `release-zlog` skill for the full workflow.

## Notes

- Versioning policy: this is the one time a bump is expected (releases only).
- After tagging, start the next dev cycle by leaving the version at 1.0.0 until the
  next release (no per-feature bumps).

## 2026-07-29 update: the tag existed but nothing was ever published

The 2026-07-01 work above tagged and pushed `v1.0.0`, but no GitHub Release was
ever actually created from it — `gh release list` came back empty, ~200 commits
of feature work landed on `main` afterward, and CHANGELOG.md still only described
the narrow initial feature set. On explicit request ("release our first version"),
resolved by moving `v1.0.0` to current `HEAD` (force-updating the pushed tag,
confirmed with the user first since that rewrites shared history) rather than
minting a new version number, since nothing had actually shipped under the old
tag yet. `__version__`/`pyproject.toml` stay at `1.0.0`. `CHANGELOG.md`'s `[1.0.0]`
entry was rewritten to cover everything now in the app, dated 2026-07-29. Also
fixed two genuinely broken tests found during the release gate (unrelated to any
single feature): `test_clear_device_button_no_device`/`_clears_view` assumed an
empty device picker, which no longer occurs now that "This PC" always occupies it
(see local-source-in-device-box.md); and `test_follow_stays_manual_and_never_yanks`
caught a real one-row lag in `_do_follow_scroll` after a large burst, fixed by
re-pinning to the bottom once more on the next event-loop turn once the
scrollbar's range has settled.
