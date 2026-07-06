# Plan: Automated release build (GitHub Actions)

- **Status:** Done
- **Owner:** Vũ
- **Created:** 2026-07-06
- **Related:** `release-1.0.0.md` (manual checklist), the `release-zlog` skill

## Goal

Push a `v*` tag → CI builds the Windows `.exe` with cx_Freeze on a Windows runner,
zips it, and attaches it to a GitHub Release automatically. Removes the manual
"build the exe on my machine and upload it" step from the release checklist.

## Scope

- **In:** a new `.github/workflows/release.yml` triggered on `v*` tags that builds
  `zlog.exe` via `cxfreeze_setup.py`, zips `build/exe.win-amd64-*`, and creates/updates
  the GitHub Release with the zip attached.
- **Out:** code signing, an installer (Inno Setup/MSI), auto-publishing to any store,
  changing the version-bump policy. No app code changes.

## Design

- `runs-on: windows-latest`.
- Steps: checkout → `astral-sh/setup-uv` → `uv python install` (reads `.python-version`
  → 3.14) → `uv sync --extra build` → `uv run --extra build python cxfreeze_setup.py build`.
- The tag is the source of truth for the version; the version already lives in
  `src/zlog/__init__.py`. Optionally verify the tag matches `__version__` and fail
  loudly on mismatch (cheap guard against tagging the wrong version).
- Package: `Compress-Archive build/exe.win-amd64-*/* zlog-<tag>-win64.zip`.
- Publish: `softprops/action-gh-release@v2` with `files: zlog-*-win64.zip`. It uses the
  built-in `GITHUB_TOKEN`; needs `permissions: contents: write`.

## Architecture touch points

- **App code:** none. This is CI/release infrastructure only.
- **Versioning:** unchanged — release-only bump policy stands; the workflow just reacts
  to the tag the human pushes.
- **cx_Freeze, not pyinstaller:** reuses the existing `cxfreeze_setup.py` (user preference).

## Risks & regressions to check

- Tag-vs-`__version__` mismatch → the guard step fails the run with a clear message.
- `build/exe.win-amd64-<pyver>` folder name embeds the Python minor version → glob with
  a wildcard, never hard-code `3.14`.
- Windows runner may not have a matching Python preinstalled → `uv python install` fetches
  it from `.python-version`.
- Workflow can't be executed from the sandbox; verify by YAML-lint + a dry logic read,
  and confirm the build command matches what `build.bat` / the release-zlog skill use.

## Verification

- [ ] `release.yml` is valid YAML (parse it)
- [ ] Build command byte-for-byte matches `build.bat` / `release-zlog` skill
- [ ] Zip glob uses a wildcard for the pyver folder
- [ ] `permissions: contents: write` present so the release can be created
- [ ] Manual: push a throwaway `v0.0.0-test` tag and confirm a draft release with the
      zip appears (user does this on their machine / GitHub)
