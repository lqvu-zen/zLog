# Plan: Offer to fetch adb when it's missing

- **Status:** Draft  <!-- Draft | Approved | In progress | Done | Abandoned -->
- **Owner:** unassigned
- **Created:** 2026-07-30
- **Related:** [usable-without-adb.md](usable-without-adb.md), [custom-adb-path.md](custom-adb-path.md), [device-picker.md](device-picker.md), [release-workflow.md](release-workflow.md)

## Goal

A user with no `adb` is **told once, clearly**, and offered two ways forward:
let zLog fetch platform-tools for them, or download it themselves. After either,
Android devices work without a restart.

## Why this shape (decision recorded)

The original idea was to **bundle** adb in the release. That's off the table for
a licensing reason, not a technical one: Google's SDK terms forbid redistributing
the platform-tools binaries — you may not "copy (except for backup purposes),
modify, adapt, redistribute … or create derivative works of the SDK or any part
of the SDK" ([platform-tools](https://developer.android.com/tools/releases/platform-tools)).
adb's *source* is Apache-2.0 in AOSP and projects like
[scrcpy](https://github.com/Genymobile/scrcpy) do ship `adb.exe` anyway, but
zLog is MIT and often lands in corporate environments — shipping a binary against
its own licence terms isn't a risk worth taking for convenience.

**Fetching on demand sidesteps it entirely: the user downloads from Google and
accepts Google's terms; zLog redistributes nothing.** Falling back to "download
it yourself" costs nothing and covers offline/locked-down machines.

Prerequisite already shipped: [usable-without-adb.md](usable-without-adb.md)
(commit `3c476ee`) means a missing adb no longer breaks the picker — this plan
builds the *recovery path* on top of that, rather than fixing brokenness.

## Scope

- **In:** detect "no adb anywhere"; a one-time, non-blocking prompt offering
  **Download for me** / **I'll do it myself** / **Not now**; a background fetch +
  verify + unzip into app data; adb resolution that prefers the user's own adb
  and falls back to the managed copy; README/GUIDE instructions (**README done**
  in this change).
- **Out (non-goals):** bundling adb in the release zip (see above), auto-updating
  the fetched copy, fetching on non-Windows (link out instead), managing the adb
  *server* lifecycle, and nagging on every launch.

## Design

Resolution is the only production logic; the rest is a dialog and a download.

**Resolution order** — the user's own adb wins, deliberately:

1. Settings override (`_adb_path_setting`) — explicit intent.
2. `adb` on **PATH** — today's behaviour, and what a dev machine expects.
3. Managed copy in app data (what we fetched).

> PATH before the managed copy is the opposite of the naive order, and it matters:
> a second adb at a different version will kill the running adb server of someone
> with Android Studio open ("adb server version doesn't match"). Never shadow an
> adb the user already has.

| File | Layer | Change |
|---|---|---|
| `src/zlog/core/adbpath.py` (new) | core | Pure, OS-free: `resolve_adb(setting, path_lookup, managed) -> (path, source)` implementing the order above and reporting **which** source won. Existence checks injected as callables, so it unit-tests with no filesystem. |
| `src/zlog/core/adbfetch.py` (new) | core | Pure: `platform_tools_url(os_name)`, and `verify_download(data, expected_sha256)`. Keeping URL-building and integrity checking pure makes them testable without network. |
| `src/zlog/ui/adb_setup_dialog.py` (new) | ui | The one-time prompt: what adb is, why it's needed (Android only), the three choices, and a link to the download page. Plain and skippable — not a wizard. |
| `src/zlog/ui/adb_fetcher.py` (new) | ui | `AdbFetcher(QThread)` — download to a temp file with progress, verify, unzip into `QStandardPaths.AppDataLocation/platform-tools`, emit `done(path)` / `error(msg)`. Same signal discipline as every other reader; cancellable. |
| `src/zlog/ui/main_window.py` | ui | `_adb_path()` delegates to `resolve_adb(...)`. On startup, **if** adb is unresolvable **and** the user hasn't been asked before, show the prompt once (a flag in settings). After a successful fetch, re-resolve and `refresh_devices()` — no restart. Status/Settings show which adb is in use. |
| `src/zlog/ui/settings_dialog.py` | ui | Show the effective adb path + source; a **Download adb…** button so it's reachable again after dismissing the prompt. |
| `README.md` | — | **Done in this change:** adb is Android-only, how to get it, how to point Settings at an existing Android Studio copy. |
| `docs/GUIDE.md` | — | Same, in the walkthrough's voice. |
| `tests/test_adbpath.py`, `tests/test_adbfetch.py` (new) | — | Order (setting > PATH > managed); missing candidates skipped; nothing found → `"adb"` so `usable-without-adb` still holds; reported `source` correct. URL per OS; verify rejects a bad hash/truncated zip. |

## Architecture touch points

- **Threading:** the download runs on a `QThread` and reaches the UI only via
  signals — same contract as the readers. It must be cancellable and must not
  block startup: the prompt appears, the app is already usable.
- **Model/proxy:** none.
- **Dependency direction:** `core/adbpath.py` and `core/adbfetch.py` are Qt-free
  and network-free (I/O injected/deferred); `ui` does the downloading. `ui → core`.

## Risks & regressions to check

- **Integrity of a downloaded binary is the top risk.** We'd be fetching an
  executable and running it. HTTPS to Google's official host only, verify a
  **pinned SHA-256**, and fail closed — never execute an unverified download.
  Pinning means the plan needs a refresh process when Google publishes a new
  platform-tools; decide who updates it (see open questions).
- **Never shadow the user's adb** (see resolution order) — the Android Studio
  server-kill scenario is the one users would hate most.
- **Corporate/offline machines**: the fetch will fail; the dialog must make
  "I'll do it myself" a first-class path, not a consolation prize.
- **Don't nag.** Ask once, record that we asked, and leave a Settings entry point.
  Re-asking every launch on a Windows-only user's machine would be obnoxious.
- **Proxy environments** may break the download — report the failure with the
  manual instructions rather than a bare stack trace.
- **Don't regress `usable-without-adb`**: with no adb and the prompt dismissed,
  the picker must still offer local sources and Start must still work.
- **Antivirus** may quarantine a freshly downloaded `adb.exe`; surface a readable
  error rather than a silent "still no adb".

## Verification

- [ ] `uv run pytest` in **one process** — new pure tests plus full suite.
- [ ] `uv run ruff check .` and `uv run ruff format --check .`
- [ ] Unit: a tampered/truncated zip fails verification and nothing is installed.
- [ ] Manual, clean Windows VM, **no adb**: launch → prompted once → "Download
      for me" → devices appear after Refresh, no restart. Relaunch → not prompted
      again.
- [ ] Manual, same VM: choose "I'll do it myself" → prompt gone, Settings →
      **Download adb…** still works.
- [ ] Manual, machine **with** Android Studio running: confirm zLog uses their
      adb (source reads "PATH") and does **not** kill their server.
- [ ] Manual, network blocked: fetch fails with the manual instructions.

## Open questions

- **Pinned hash maintenance:** platform-tools updates often. Pin a known-good
  version and refresh it during releases, or verify against Google's published
  checksum at fetch time? Leaning pin-and-refresh — simpler to reason about, and
  a slightly old adb is fine since we prefer the user's own anyway.
- **Which Windows arch/OS to offer?** Leaning Windows-only fetch initially, with
  macOS/Linux getting the link and instructions (their package managers are
  better at this than we are).
- **Where to install:** app data (per-user, no admin) vs. beside the exe (breaks
  on a read-only install dir). Leaning app data.
- Should **This PC**-only users ever see the prompt? Arguably not — but we can't
  know their intent at first launch. Leaning: show once, worded so it's obviously
  skippable and Android-specific.
