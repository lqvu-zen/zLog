# Plan: Ship adb inside the release package

- **Status:** Draft  <!-- Draft | Approved | In progress | Done | Abandoned -->
- **Owner:** unassigned
- **Created:** 2026-07-30
- **Related:** [usable-without-adb.md](usable-without-adb.md), [custom-adb-path.md](custom-adb-path.md), [device-picker.md](device-picker.md), [release-workflow.md](release-workflow.md)

## Goal

Download zLog, unzip, plug in a phone, press **Start** — Android logging works
with **no separate platform-tools install and no PATH setup**.

## Why

Requiring users to install Android SDK platform-tools and get `adb` onto PATH is
the single biggest setup barrier for the Android half of zLog. It's also
avoidable: the app already knows how to invoke an adb at an arbitrary path
(`custom-adb-path` shipped that), so bundling one is mostly a build + resolution
change, not new capability.

## ⚠️ Licensing — read this before approving

**This is the decision that shapes the whole plan, and it isn't a technical one.**

Google's SDK terms covering the platform-tools **binaries** prohibit
redistribution: you may not "copy (except for backup purposes), modify, adapt,
redistribute … or create derivative works of the SDK or any part of the SDK"
([Android SDK licence terms, as summarised in the platform-tools
docs](https://developer.android.com/tools/releases/platform-tools)). So we
**cannot** simply drop Google's `adb.exe` into the zip and ship it.

However, **adb's source is part of AOSP and is Apache-2.0 licensed**
([Android Debug Bridge](https://en.wikipedia.org/wiki/Android_Debug_Bridge)),
and the well-known precedent is **scrcpy**, which is Apache-2.0 and *does*
include `adb.exe` in its Windows releases so it "works out-of-the-box"
([scrcpy](https://github.com/Genymobile/scrcpy)).

So the routes differ mainly in legal exposure, not difficulty:

| Route | How | Legal position |
|---|---|---|
| **A. Bundle Google's binary** | copy `adb.exe` + its 2 DLLs into the zip | **Contrary to the SDK terms as written.** Widely done in practice (scrcpy et al.), but "others do it" is not a licence. |
| **B. Bundle an Apache-2.0 build** | build adb from AOSP source (or use a reputable Apache-2.0-licensed prebuilt), ship with its LICENSE/NOTICE | **Clean**, but we own the build, the updates, and the CI cost. |
| **C. Fetch on first run** | app downloads platform-tools from Google on demand, into app data | **Clean** — the *user* accepts Google's terms, we redistribute nothing. Needs network, adds a first-run step. |
| **D. Don't bundle; just make it painless** | detect common install locations, one-click "Download adb" that opens Google's page, clear Settings path | **Clean**, zero risk, least magic. |

**Recommendation: decide the route first.** My leaning is **C or D**, with **B**
if bundling is genuinely required — because zLog is MIT-licensed and shipping a
binary against its own licence terms is a real (if commonly ignored) risk for
something people put in corporate environments. This plan is written so the
**resolution work is shared by all four**, and only the acquisition step differs.

## Scope

- **In:** an adb *resolution order* that prefers a bundled/managed adb, falls
  back to PATH, and is overridable in Settings; the packaging hook to place the
  binary; a visible indicator of which adb is in use; docs/licence attribution.
- **Out (non-goals):** shipping adb for Linux/macOS (Windows release only for
  now), bundling the full platform-tools suite (only `adb` + the DLLs it needs),
  auto-updating the bundled adb, and starting/stopping the adb **server** any
  differently than today.

## Design

The one real code change is where `_adb_path()` looks. Everything else is
packaging and messaging.

**Resolution order** (first hit wins), so a user can always override and a
bundled copy never silently shadows a deliberate choice:

1. Settings override (`_adb_path_setting`) — explicit user intent.
2. Bundled adb next to the executable (`<app dir>/platform-tools/adb.exe`).
3. Managed copy in app data (route C's download target).
4. `adb` from PATH — today's behaviour, and what a developer machine expects.

| File | Layer | Change |
|---|---|---|
| `src/zlog/core/adbpath.py` (new) | core | Pure, OS-free: `resolve_adb(setting, bundled, managed, path_lookup) -> (path, source)` implementing the order above, returning **which** source won so the UI can say so. Takes existence checks as callables, so it unit-tests with no filesystem. |
| `src/zlog/ui/main_window.py` | ui | `_adb_path()` delegates to `resolve_adb(...)`, passing real locations (`Path(sys.executable).parent / "platform-tools"`, `QStandardPaths.AppDataLocation`). Status/Settings show the resolved source ("using bundled adb" / "using adb from PATH"). |
| `cxfreeze_setup.py` | — | `build_exe_options["include_files"]` to copy `platform-tools/` into the build output (route A/B). Absent the directory, the build must still succeed — bundling is optional, not a build dependency. |
| `.github/workflows/release.yml` | — | Acquire adb for the chosen route before building (B: build/fetch the Apache-2.0 artifact; A: download platform-tools), and include its `LICENSE`/`NOTICE` in the zip. |
| `src/zlog/ui/settings_dialog.py` | ui | Show the effective adb path + source, with the override field; a "Download adb" action if route C/D. |
| `docs/GUIDE.md`, `README.md`, `NOTICE` (new) | — | State what's bundled, its licence and origin. Required for B, good practice for any route. |
| `tests/test_adbpath.py` (new) | — | Order: setting beats bundled beats managed beats PATH; missing candidates are skipped; nothing found → plain `"adb"` (today's behaviour, so `usable-without-adb` still applies); the reported `source` is right in each case. |

## Architecture touch points

- **Threading:** none — resolution is a few path checks at call time. Cache the
  result but allow **Refresh** to re-resolve, so installing adb mid-session works.
- **Model/proxy:** none.
- **Dependency direction:** `core/adbpath.py` is Qt-free and filesystem-free
  (callables injected); the window supplies real paths. `ui → core` holds.

## Risks & regressions to check

- **Licensing (above) is the top risk** — this is the one that can't be fixed
  later by a patch release. Decide the route explicitly and record it here.
- **Package size:** platform-tools adds several MB (adb.exe + `AdbWinApi.dll` +
  `AdbWinUsbApi.dll`). Acceptable, but the zip grows and needs the DLLs — adb
  alone won't run on Windows without them.
- **Version skew:** a bundled adb older than the user's device/daemon can cause
  "adb server version doesn't match" and *kill their existing adb server*. This
  is the nastiest practical failure: a developer with Android Studio running
  would have their environment disrupted by our copy. Strongly argues for
  **PATH-first** on machines that already have adb — reconsider the order above
  if this proves common.
- **Antivirus/SmartScreen:** shipping an extra unsigned .exe in the zip raises
  the flag rate on an already-unsigned build.
- **Don't break the no-adb fix:** [usable-without-adb.md](usable-without-adb.md)
  must still hold when nothing resolves — the picker stays usable for local
  sources.
- **`_adb_path` is called on every adb operation** — keep resolution cheap
  (cached), not a stat storm per call.
- Frozen-app path detection differs between `python -m zlog` and the cx_Freeze
  exe; `sys.executable` means different things. Verify both.

## Verification

- [ ] `uv run pytest` in **one process** — new `test_adbpath.py` plus full suite.
- [ ] `uv run ruff check .` and `uv run ruff format --check .`
- [ ] Build the exe and confirm `platform-tools/` lands beside it and is used.
- [ ] Manual on a **clean Windows VM with no adb and no Android Studio**: unzip,
      plug in a phone, Start → logs stream. This is the whole point of the plan
      and the only test that proves it.
- [ ] Manual on a machine that **already has adb** (Android Studio running):
      confirm we don't kill or conflict with their adb server.
- [ ] Confirm the zip contains the adb licence/NOTICE.

## Open questions

- **Which route (A/B/C/D)?** Blocking — everything else follows from it.
- **PATH before bundled, or bundled before PATH?** The version-skew risk argues
  for preferring an adb the user already has. Leaning: PATH first *if present*,
  bundled as the fallback — the opposite of the order sketched above. Worth
  deciding with the route.
- **Windows only, or Linux/macOS too?** Leaning Windows-only first: it's the
  primary target and the only release artifact today.
- Should a bundled adb be **opt-out** in Settings for users who distrust it?
