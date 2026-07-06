---
name: release-zlog
description: 'Cut a versioned release of the zLog desktop app and build its Windows executable with cx_Freeze. Use this whenever the user wants to ship, release, tag, or publish a new version of zLog — e.g. "cut the 1.1 release", "build the exe", "make a Windows build", "ship a new version", "tag a release", or "publish zLog on GitHub". This skill carries the release gate (tests + lint), the version-bump rule (versions change only at release), the CHANGELOG update, the cx_Freeze build, and the tag/GitHub-release steps. Do NOT use it to add a feature (use add-zlog-feature) or to just run the app (use run-zlog).'
---

# Releasing zLog

zLog follows a **release-only versioning** rule: `__version__` (`src/zlog/__init__.py`)
and `version` (`pyproject.toml`) change **only** when cutting a release — never per
feature or fix. This skill is that moment.

The Windows executable is built with **cx_Freeze** via `cxfreeze_setup.py` (or the
convenience `build.bat`). The actual build must run on **Windows** to produce a
`.exe`; the rest (gate, version, CHANGELOG, tag) is cross-platform.

## Where things live

| Concern | File |
|---|---|
| version strings | `src/zlog/__init__.py` (`__version__`), `pyproject.toml` (`version`) |
| release notes | `CHANGELOG.md` |
| cx_Freeze build config | `cxfreeze_setup.py` |
| one-click build | `build.bat` |
| release checklist plans | `docs/plans/release-<version>.md` |

## The workflow

### 1. Release gate — everything must be green

```bash
cd D:/Projects/zLog
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

Also confirm every plan in `docs/plans/` intended for this release is **Done**. If
anything is red or unfinished, stop and fix it before releasing.

### 2. Pick the version and bump both files

Choose the version per SemVer (breaking → major, features → minor, fixes → patch).
Set it in **both** places (they must match):

- `src/zlog/__init__.py` → `__version__ = "<X.Y.Z>"`
- `pyproject.toml` → `version = "<X.Y.Z>"`

This is the *only* time these change. Don't bump anything else.

### 3. Update the CHANGELOG

Add a `## [<X.Y.Z>] — <YYYY-MM-DD>` section to `CHANGELOG.md` (Keep a Changelog
style), grouping the notable changes since the last release. Update the link
reference at the bottom to the new tag.

### 4. Lock, then build the executable (on Windows)

```powershell
uv lock                                  # refresh the lockfile for this version
uv run --extra build python cxfreeze_setup.py build
# or: build.bat
```

cx_Freeze writes to `build\exe.win-amd64-<pyver>\` — the app is `zlog.exe` plus its
bundled Qt runtime. `cxfreeze_setup.py` uses the `Win32GUI` base (no console window)
and relies on cx_Freeze's PySide6 hook to pull in the Qt plugins/libraries.

**Smoke-test the build:** run `build\exe.win-amd64-<pyver>\zlog.exe` and confirm the
window opens and (with a device attached) streaming works. Zip the whole
`exe.win-amd64-<pyver>` folder for distribution — the `.exe` needs the sibling files.

Troubleshooting cx_Freeze + PySide6:
- Missing Qt plugin at runtime → add it under `build_exe_options["include_files"]` or
  ensure a recent cx_Freeze whose PySide6 hook covers it.
- "Failed to execute script" → run the exe from a terminal to see the traceback; a
  missing module usually means adding it to `packages`/`includes`.
- Use a cx_Freeze release that supports the project's Python (see `.python-version`).

### 5. Commit, tag, and push

```bash
cd D:/Projects/zLog
git add -A
git commit -m "Release <X.Y.Z>"
git tag -a v<X.Y.Z> -m "zLog <X.Y.Z>"
git push
git push --tags
```

### 6. Publish the GitHub release

**Automated (preferred).** Pushing the `v<X.Y.Z>` tag in step 5 triggers
`.github/workflows/release.yml`: a Windows runner builds the exe with cx_Freeze,
zips `exe.win-amd64-*`, and creates the GitHub Release with the zip attached. The
workflow first fails loudly if the tag doesn't match `__version__`. Just watch the
Actions tab; no manual upload needed.

**Manual fallback** (if you built locally in step 4 and want to publish by hand):
create a release for tag `v<X.Y.Z>`, paste the CHANGELOG section as the notes, and
attach the zipped `exe.win-amd64-*` folder. With the GitHub CLI:

```powershell
gh release create v<X.Y.Z> build\zlog-<X.Y.Z>-win64.zip --title "zLog <X.Y.Z>" --notes-file CHANGELOG.md
```

### 7. Record it

Flip the release plan (`docs/plans/release-<version>.md`) to **Done** and tick its
boxes. Leave the version as-is until the next release (no post-release bump).

## Notes

- The build is Windows-only for a `.exe`; on Linux/macOS cx_Freeze produces a native
  binary instead (`base=None`), useful for a local smoke test but not the Windows
  artifact.
- Keep `cxfreeze_setup.py` minimal; add includes only when a real runtime error
  proves they're needed.
