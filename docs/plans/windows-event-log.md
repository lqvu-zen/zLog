# Plan: Windows Event Log as a log source

- **Status:** Done  <!-- Draft | Approved | In progress | Done | Abandoned -->
- **Owner:** unassigned
- **Created:** 2026-07-24
- **Related:** [windows-debug-output.md](windows-debug-output.md), [windows-app-focus.md](windows-app-focus.md), [merged-multi-device.md](merged-multi-device.md)

## Goal

Stream the Windows Event Log (Application / System / Security and other channels)
into a zLog tab, with the same view, query bar, filters, and export the Android
and debug-output sources already have.

## Why

`OutputDebugString` capture covers apps that trace at runtime; the Event Log is
where **crashes, service failures, driver and OS-level events** land — including
for apps that never call `OutputDebugString`. Together they cover "what happened
to this app" from both ends.

## Scope

- **In:** a source that streams a chosen Event Log channel, mapping each event to
  `LogEntry`; a channel picker; live subscription plus an initial "last N events"
  backfill.
- **Out (non-goals):** writing/clearing the Event Log, remote-machine channels,
  ETW real-time providers (see [etw-tracing.md](etw-tracing.md)), and custom XPath
  filter strings (the query bar already filters).

## Design

Events map cleanly onto `LogEntry`, so nothing in the model/proxy/delegate/query
changes — this is a reader plus a parser, exactly like the DBWIN work.

Mapping (from an event's rendered System XML):
- **Level** 1 Critical→`F`, 2 Error→`E`, 3 Warning→`W`, 4 Information→`I`,
  5 Verbose→`V`, so `LEVEL_RANK` and the min-level filter work unchanged.
- **Provider Name** → `tag` (so `tag:`, mute-tag, Tag Summary work).
- **Execution @ProcessID / @ThreadID** → `pid` / `tid`.
- **TimeCreated @SystemTime** → `time`, formatted `MM-DD HH:MM:SS.mmm` to match
  logcat so `since:`/`until:` and Go-to-time keep working.
- Rendered message → `message`; `source` stamps the channel name.

| File | Layer | Change |
|---|---|---|
| `src/zlog/core/winevent.py` (new) | core | Pure, **OS-free** (stdlib `xml.etree` only): `map_level(n)`, `format_event_time(iso)`, `parse_event_xml(xml) -> LogEntry`. Unit-tested against fixture XML, so it runs on Linux/CI like `core/dbwin.py`. |
| `src/zlog/winlog/evtlog_reader.py` (new) | winlog | `EventLogReader(QThread)` with the usual `batch_ready`/`error` contract. Live path: `win32evtlog.EvtSubscribe` (pywin32) pushing new events → `core.winevent` → batched with the shared cadence. pywin32 imported lazily **inside** `run()`; off Windows (or without pywin32) it emits a clear error and returns. |
| `src/zlog/winlog/channels.py` (new) | winlog | A curated default channel list (Application, System, Security, Setup) plus an "other…" free-text entry; optionally enumerate via `wevtutil el`. |
| `src/zlog/ui/main_window.py` | ui | **File → Capture Event Log…** → channel picker → reuse-or-new tab → `capture.attach(sess, EventLogReader(channel), stream_label=channel)`. Teardown is already handled by `capture.detach`. |
| `pyproject.toml` | — | `pywin32; sys_platform == "win32"` (optional, platform-gated) so Linux/CI never installs it. |
| `docs/GUIDE.md`, `tests/test_winevent.py` (new) | — | Guide section; tests for level/time mapping and `parse_event_xml` over Application/System/Security fixtures, an event with no PID, and unparseable XML. |

## Architecture touch points

- **Threading:** all work off-thread, UI reached only via signals; attaches
  through `CaptureController` so Stop tears it down with everything else.
- **Model/proxy:** none new; every existing gate applies.
- **Dependency direction:** `ui → winlog → core`; `core/winevent.py` imports
  neither Qt nor pywin32.

## Risks & regressions to check

- **New dependency:** pywin32 is Windows-only and platform-gated — verify Linux
  install and the full test suite are unaffected, and that selecting the source
  off Windows reports cleanly rather than crashing.
- **Security channel needs elevation** — a subscribe failure must report, not hang.
- **Volume:** System/Security can be very chatty; confirm batching + the ring cap.
- **Missing year:** logcat's format has no year either; `since:`/`until:` compare
  time-of-day, so a long capture spanning midnight behaves as it does today.
- **Message rendering** can be slow per event (it resolves provider metadata);
  keep it off the UI thread and consider caching per provider.

## Verification

- [x] `uv run pytest` (new `test_winevent.py`; suites green — this dev box is
      Windows, so the pywin32-backed reader ran for real too, see below)
- [x] `uv run ruff check .` and `uv run ruff format --check .`
- [x] Manual on Windows: streamed the real Application channel end to end
      (backfill of 5, then `start()`/`stop()` with no hang, no error) — see
      Implementation notes.

## Resolved

- **pywin32 vs. stdlib:** pywin32, as leaned — added to `pyproject.toml`
  `dependencies` with a `sys_platform == 'win32'` marker (not a separate
  extra), so `uv sync` installs it automatically on Windows and skips it
  entirely elsewhere with zero setup steps for the primary (Windows) audience.
- **EventID:** message prefix (`[1000] …`), as leaned — `tag` stays just the
  provider name so `tag:`/mute-tag/Tag Summary keep working unchanged.
- **Backfill:** 200 by default (`EventLogReader.__init__(backfill=200)`), as
  leaned. Exposed as a constructor arg, not yet a Settings field — cheap to
  add later if wanted.
- **Message rendering (not in the original open questions, found during
  implementation):** the plan's design section assumed a human-readable
  rendered message would be available; in practice `EvtRender(...,
  EvtRenderEventXml)` only returns the raw System XML — the friendly message
  text requires a *separate* `EvtFormatMessage` call against the provider's
  metadata handle, which is exactly the "can be slow per event, consider
  caching" risk the plan already flagged. Scoped that out of this pass:
  `core/winevent.parse_event_xml` builds the message from the event's own
  `<EventData><Data>` values (prefixed with `[EventID]`), which is always
  present and needs no extra Win32 call. A real capture (see below) shows
  this is usably readable, if less polished than Event Viewer's rendered
  text. Follow-up if wanted.

## Implementation notes

- Real end-to-end smoke test on this (Windows) dev machine, run directly
  against the live Application log — not just unit tests:
  `EventLogReader("Application", backfill=5).start()` for 3s then `.stop()`
  produced one batch of 5 real `LogEntry` rows and zero errors, confirming
  backfill, the live-subscription setup, and clean teardown all work against
  the real Win32 APIs, not just mocks.
- `tests/test_evtlog_reader.py::test_reports_cleanly_without_pywin32` forces
  the "pywin32 missing" branch via `monkeypatch.setitem(sys.modules,
  "win32evtlog", None)` rather than relying on pywin32 actually being absent
  — needed once pywin32 became a real (now-installed) dependency here, and
  more robust regardless: it exercises the same code path on any OS.
- A real bug surfaced by testing on Windows rather than assuming: the first
  cut of the "off-Windows" `MainWindow.capture_event_log()` test asserted
  behavior only `if sys.platform != "win32"`, so on this real Windows runner
  the guarded assertions never ran *and* the un-mocked call fell through to a
  real, blocking `QInputDialog.getItem()` — hanging the test under the
  offscreen platform (no user to click it). Fixed by forcing
  `is_supported()` to `False` via monkeypatch instead of branching on the
  real platform, so the "unsupported" path is exercised deterministically
  everywhere and the dialog is never reached in that test.
