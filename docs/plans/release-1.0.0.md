# Plan: Cut the 1.0.0 release

- **Status:** In progress  <!-- Draft | Approved | In progress | Done | Abandoned -->
- **Owner:** Vũ
- **Created:** 2026-07-01

## Goal

Ship zLog 1.0.0: the first stable, tagged release with a Windows executable.

## Steps

- [x] Bump `__version__` (`src/zlog/__init__.py`) and `version` (`pyproject.toml`) to `1.0.0`.
- [x] Write `CHANGELOG.md` for 1.0.0.
- [x] Release gate: `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .` all green.
- [ ] (your machine) `uv lock` so the lockfile matches Python 3.14 + version 1.0.0.
- [ ] (your machine) Commit everything, then tag and push:
      `git tag -a v1.0.0 -m "zLog 1.0.0"` and `git push --tags`.
- [ ] (your machine) Build the Windows exe (see below) and attach it to the GitHub release.
- [ ] (your machine) Create the GitHub Release for `v1.0.0` using the notes below.

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
