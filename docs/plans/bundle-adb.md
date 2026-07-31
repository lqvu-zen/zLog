# Plan: Offer to fetch adb when it's missing

- **Status:** Done  <!-- Draft | Approved | In progress | Done | Abandoned -->
- **Owner:** unassigned
- **Created:** 2026-07-30
- **Related:** [usable-without-adb.md](usable-without-adb.md), [custom-adb-path.md](custom-adb-path.md), [device-picker.md](device-picker.md), [release-workflow.md](release-workflow.md)

## Goal

**A user who is trying to use an Android device** and has no `adb` is told
clearly, once, and offered two ways forward: let zLog fetch platform-tools for
them, or download it themselves. After either, devices appear without a restart.

**Audience:** Android users only. Someone using zLog purely for Windows debug
output, a launched app, or a followed log file should never be asked about adb —
they have no use for it, and [usable-without-adb.md](usable-without-adb.md)
already makes those flows work without it.

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

**When the prompt appears — on Android intent, not at launch.** A startup prompt
would interrupt every Windows-only user with a question about tooling they don't
need, which is exactly the audience this plan excludes. Instead it fires the
first time the user *asks for something Android* and adb is unresolvable:

- pressing **Refresh** on the device picker,
- picking an Android device entry (they can't — the list is empty — but a Wi-Fi
  **Connect…** attempt counts),
- **Capture dumpsys…**, or any other adb-backed action.

Cold start stays silent: the existing one-line status note from
`usable-without-adb` is enough for someone who never touches Android. Record
"already asked" in settings so a declined prompt doesn't reappear on the next
Refresh; **Settings → Download adb…** remains the way back in.

| File | Layer | Change |
|---|---|---|
| `src/zlog/core/adbpath.py` (new) | core | Pure, OS-free: `resolve_adb(setting, path_lookup, managed) -> (path, source)` implementing the order above and reporting **which** source won. Existence checks injected as callables, so it unit-tests with no filesystem. |
| `src/zlog/core/adbfetch.py` (new) | core | Pure: `platform_tools_url(os_name)`, and `verify_download(data, expected_sha256)`. Keeping URL-building and integrity checking pure makes them testable without network. |
| `src/zlog/ui/adb_setup_dialog.py` (new) | ui | The one-time prompt: what adb is, why it's needed (Android only), the three choices, and a link to the download page. Plain and skippable — not a wizard. |
| `src/zlog/ui/adb_fetcher.py` (new) | ui | `AdbFetcher(QThread)` — download to a temp file with progress, verify, unzip into `QStandardPaths.AppDataLocation/platform-tools`, emit `done(path)` / `error(msg)`. Same signal discipline as every other reader; cancellable. |
| `src/zlog/ui/main_window.py` | ui | `_adb_path()` delegates to `resolve_adb(...)`. **Trigger on Android intent, never on startup** (see below). After a successful fetch, re-resolve and `refresh_devices()` — no restart. Status/Settings show which adb is in use. |
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

- [x] Targeted tests only (`tests/test_adbpath.py`, `test_adbfetch.py`,
      `test_adb_fetcher.py`, `test_adb_setup_prompt.py`,
      `test_main_window_adb.py`, `test_main_window_settings.py`,
      `test_settings_dialog.py`, `test_main_window_dbwin.py`) — 138 passed.
      Full-suite run deferred to a release/QA pass, not per-feature (see
      [[no-full-suite-per-feature]]).
- [x] `uv run ruff check .` and `uv run ruff format --check .` — both clean,
      whole repo.
- [x] Unit: a tampered/truncated zip fails verification and nothing is
      installed (`test_adbfetch.py`, `test_adb_fetcher.py`), plus a
      path-traversal entry in an otherwise hash-verified archive is rejected
      (`test_path_traversal_in_archive_is_rejected`).
- [x] Manual, this machine, **real adb genuinely stripped from PATH** (not a
      separate VM, but the same effect — confirmed via `shutil.which("adb")
      is None`): launch → **no prompt** (0 dialog calls). User-initiated
      Refresh → prompted → "Download for me" → the **real** platform-tools zip
      (downloaded fresh, sha256 matched the pinned hash) was fetched via a
      network-stubbed `urlopen` (no live network call, but genuine bytes),
      verified, and installed; `_resolve_adb()` then read `("...adb.exe",
      "managed")` and the freshly-installed **real** adb.exe successfully
      executed (`adb devices` → "0 device(s) found.", no error) — the fetched
      binary actually works, not just extracts.
- [x] Manual, same setup, **relaunch with a managed copy already on disk**:
      adb resolves via "managed" immediately; the setup prompt is never
      shown again (0 calls) — confirms "asked once" survives across restarts
      once adb resolves for any reason, not just via the settings flag.
- [x] Manual, same setup, **network failure during fetch** (`urlopen` raising
      `OSError`): no crash; status bar shows "Download failed: ...";
      `_adb_fetcher` is cleared so a retry isn't blocked.
- [x] Unit: "I'll do it myself" opens the download page and marks asked
      (`test_manual_choice_opens_the_download_page`); Settings → **Download
      adb…** works even after the intent prompt was already asked/declined
      (`test_settings_download_button_bypasses_the_asked_gate`).
- [x] Unit: a Windows-only user's actions (This PC / Launch App… / Follow
      File…) never reach `_adb_path()`/`_run_adb` at all — verified by
      inspection (none of `start()`'s local-source branch, `capture_debug_
      output`, the launcher, or the file-follow path call `_adb_path` or
      `_run_adb`), so `_maybe_offer_adb_setup` can't fire from them.
- [ ] Manual, machine **with Android Studio actually running**: not performed
      (no such machine available here). The resolution *order* itself is
      directly unit-tested (`test_path_wins_over_managed`) and the real
      PATH-adb-wins behavior was exercised live in the prerequisite
      usable-without-adb.md verification — but the specific "doesn't kill an
      already-running adb server" claim wasn't observed with Android Studio
      itself. Flagging in case you want to confirm this by hand.

## Open questions (resolved)

- **Pinned hash maintenance:** Pin-and-refresh — a known-good platform-tools
  version/hash is pinned in the repo and refreshed manually during releases.
  Simpler to reason about, and a slightly old adb is fine since the user's own
  adb always wins anyway.
- **Which Windows arch/OS to offer?** Windows-only fetch initially; macOS/Linux
  get the link and manual instructions (their package managers already handle
  this better).
- **Where to install:** Per-user app data
  (`QStandardPaths.AppDataLocation/platform-tools`) — no admin rights needed,
  works even when zLog itself is installed to a read-only directory.
- ~~Should **This PC**-only users ever see the prompt?~~ **Resolved: no.** The
  plan is for Android-aimed users. We can't know intent at launch, so don't guess
  — wait until the user performs an Android action, which *is* the signal. Cold
  start stays silent.
