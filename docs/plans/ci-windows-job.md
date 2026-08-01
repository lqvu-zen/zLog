# Plan: Run CI on Windows

- **Status:** In progress  <!-- Draft | Approved | In progress | Done | Abandoned -->
- **Owner:** unassigned
- **Created:** 2026-08-01
- **Related:** [windows-debug-output.md](windows-debug-output.md), [windows-event-log.md](windows-event-log.md), [windows-app-focus.md](windows-app-focus.md), [release-workflow.md](release-workflow.md)

## Goal

CI runs the suite on **Windows** as well as Linux, so the platform zLog is built
for is actually exercised before release.

## Why — the biggest coverage gap we have

`ci.yml` runs `ubuntu-latest` only. `release.yml` uses `windows-latest`, but only
to *build* the exe — it runs no tests. So **754 lines** of Windows-only code has
never been executed by an automated run on any machine:

| Module | What's untested in CI |
|---|---|
| `winlog/dbwin_reader.py` | the DBWIN buffer/event loop |
| `winlog/evtlog_reader.py` | `EvtSubscribe` wiring |
| `winlog/processes.py` | Toolhelp process enumeration |
| `winlog/procnames.py` | PID→image-name resolution |
| `core/dbwin.py`, `core/winevent.py` | the `os.name == "nt"` branches |

The pure parsers *are* covered — the `core/` split was deliberate and it works.
What's uncovered is every `ctypes`/pywin32 call site: struct layouts, handle
lifetimes, and the 11 platform-conditional branches. Those are exactly where this
class of bug lives, and today only a manual check on your machine catches them.

We've already been bitten twice by "works on Linux, wrong on Windows" logic: the
`st_ctime` meaning difference in `file_key` (POSIX change-time vs. Windows
creation-time) and the `refresh_devices` early-return that only mattered on a
Windows box with no adb.

## Scope

- **In:** a `windows-latest` job in `ci.yml` running the same lint + test
  commands; whatever `pytest` markers/skips are needed so Windows-only tests run
  there and are skipped elsewhere (and vice versa).
- **Out (non-goals):** macOS CI, running the *interactive* Win32 captures in CI
  (a DBWIN capture needs a cooperating writer; an ETW session needs elevation),
  GUI screenshot comparison, and making the manual Windows smoke test obsolete —
  this narrows it, it doesn't replace it.

## Design

Mostly config. The suite is already headless (`QT_QPA_PLATFORM=offscreen`) and
platform-guarded, so the main work is making the matrix honest about what runs
where.

| File | Change |
|---|---|
| `.github/workflows/ci.yml` | Add a `strategy.matrix.os: [ubuntu-latest, windows-latest]` (or a second job). Linux keeps the `apt-get` Qt-libs step; Windows needs none. Both run `ruff check`/`format --check` and `uv run pytest -q`. |
| `tests/conftest.py` | A `windows_only` marker (skip unless `sys.platform == "win32"`) so genuinely-Win32 tests can exist without failing the Linux job. |
| existing Windows tests | Several currently force `is_supported() -> True` to exercise logic cross-platform. Keep those — they're the right call — but **add** a small number of genuinely-native tests behind `windows_only`: `list_processes()` returns a non-empty list containing the current process; `file_key` distinguishes two real files; `procnames.name_for(os.getpid())` resolves. |
| `docs/CONTRIBUTING.md` (if present) / `CLAUDE.md` | Note that CI is now two-platform and what each covers. |

## Architecture touch points

- **Threading / model / dependency direction:** unchanged. This is CI config plus
  a handful of native assertions.

## Risks & regressions to check

- **The Windows job may fail immediately** on things Linux never exercised —
  that's the point, but budget for a first red run and fix-forward rather than
  assuming it goes green.
- **Path assumptions** (`/tmp`, `:` separators, case-insensitive filenames) in
  tests are the likeliest first failures.
- **Line endings**: the Windows checkout will produce CRLF; without
  [gitattributes-line-endings.md](gitattributes-line-endings.md) landing first,
  `ruff format --check` may fail on Windows for line-ending reasons alone. **Do
  that plan first** — it's 10 minutes and it unblocks this one.
- **CI minutes**: Windows runners are billed at a higher rate. For a repo this
  size it's minor, but note it.
- **Don't let the Windows job become "allowed to fail"** — a permanently-yellow
  job is worse than none.

## Verification

- [ ] Both jobs green on a PR — **not yet checked**: this work is still local
      (5+ unpushed commits on `main` as of writing), and pushing/opening a PR
      needs your go-ahead first, same as the release hold. Everything below is
      verified locally on this real Windows machine instead.
- [x] Deliberately broke a Windows-only path (offset `processes.py`'s pid by
      +999999) → `test_list_processes_contains_this_process` failed with a
      clear assertion; reverted, re-ran, 3/3 passed again. This is the local
      proxy for "the job is worth having" — the real CI proof still needs a
      pushed run.
- [ ] `windows_only` skip-on-Linux — not directly checkable on this Windows
      machine; the hook logic (`if sys.platform == "win32": return` before
      skipping) is straightforward enough to trust, but flagging as unverified
      until a real Linux run confirms it.
- [ ] Total CI wall-clock — unknown until a real run.

## Open questions

- **Matrix or separate job?** Matrix is tidier; a separate job lets Windows skip
  the Qt-libs install step cleanly. Leaning matrix with a conditional step.
- Should the Windows job also run the `run-zlog` screenshot driver as a smoke
  test? Tempting, but headless rendering differs per platform — leaning no.
