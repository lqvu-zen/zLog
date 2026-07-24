# Plan: Windows Event Log as a log source

- **Status:** Draft  <!-- Draft | Approved | In progress | Done | Abandoned -->
- **Owner:** unassigned
- **Created:** 2026-07-24
- **Related:** [device-tabs.md](device-tabs.md), [merged-multidevice.md](merged-multidevice.md), [open-in-new-tab.md](open-in-new-tab.md)

## Goal

Stream the Windows Event Log (Application / System / Security and other channels)
into a zLog tab, using the same view, query bar, filters, and export the Android
logcat side already has.

## Scope

- **In:** a new *source* alongside adb devices — pick a Windows Event Log channel,
  Start/Stop streaming it live, and see events as `LogEntry` rows. A pure,
  OS-free XML→`LogEntry` parser in `core/`; a Windows-only reader thread in a new
  `winlog/` package mirroring `AdbReader`'s signal contract; a channel picker
  wired into the existing device/source bar and per-tab session.
- **Out (non-goals):** per-process stdout/stderr capture (launch-and-capture),
  filtering events by a single PID beyond the existing `pid:` query token, and
  ETW real-time provider tracing. Those stay in [backlog.md](backlog.md) as
  separate, bigger features. No cross-OS event streaming (Windows only).

## Design

Windows events map cleanly onto the existing `LogEntry(time, pid, tid, level,
tag, message, source)`, so the model, `LogFilterProxy`, delegate, query language,
presets, histogram, heat marks, and incident detection all work unchanged. Only a
new reader + parser + a source selector are needed.

Mapping (from the event's rendered System XML):
- **Level** 1 Critical→`F`, 2 Error→`E`, 3 Warning→`W`, 4 Information→`I`,
  5 Verbose→`V` (no `D`), feeding `LEVEL_RANK` / the min-level filter as-is.
- **Provider Name** → `tag` (so `tag:`, mute-tag, Tag Summary work).
- **Execution @ProcessID / @ThreadID** → `pid` / `tid`.
- **TimeCreated @SystemTime** → `time`, formatted as the existing
  `"MM-DD HH:MM:SS.mmm"` string so current time handling stays happy.
- Rendered message text → `message` (EventID folded into the message or tag —
  see open questions).
- `source` stamps the channel name (e.g. `System`) so a merged Android+Windows
  tab can tell rows apart, exactly like the merged multi-device view.

| File | Layer | Change |
|---|---|---|
| `src/zlog/core/winevent.py` (new) | core | Pure, **OS-free** (stdlib `xml.etree` only, no pywin32): `LEVEL_MAP` + `map_win_level(n)`; `format_win_time(iso) -> "MM-DD HH:MM:SS.mmm"`; `parse_event_xml(xml: str) -> LogEntry`. Unit-tested with fixture XML — runs on Linux/CI. |
| `src/zlog/winlog/__init__.py`, `src/zlog/winlog/reader.py` (new) | winlog (peer of `adb/`) | `WinEventReader(QThread)` with the **same signals** as `AdbReader`: `batch_ready(list[LogEntry])`, `error(str)`, `stream_ended()`. Live path: pywin32 `win32evtlog.EvtSubscribe` (push callback) → parse each event's XML via `core.winevent` → batch with the existing `should_flush` cadence. pywin32 imported lazily **inside** `run()`; on non-Windows (or missing pywin32) emit a clear `error` and return. `stop()` cancels the subscription and `wait()`s. |
| `src/zlog/winlog/channels.py` (new) | winlog | Enumerate available channels (a curated default set: Application, System, Security, Setup; optionally `wevtutil el` for the full list). Pure list building where possible. |
| `src/zlog/ui/device_controller.py` / `ui/main_window.py` | ui | Generalize "device" → "source": the source picker offers connected adb devices **and** Windows channels; Start routes to `AdbReader` or `WinEventReader` accordingly. Each tab/`LogSession` already owns its reader, so a Windows tab sits next to an Android tab with no session changes. Reuse `_set_tab_label` (channel name as the tab title; `● <channel>` while streaming). |
| `pyproject.toml` | — | Add `pywin32; sys_platform == "win32"` (optional, platform-gated) so Linux/CI never installs it and the guarded import path is exercised. |
| `docs/GUIDE.md` | — | A short "Windows Event Log" section: pick a channel, Start, filter/query as usual. |
| `tests/test_winevent.py` (new) | — | Level/time mapping, `parse_event_xml` over fixture XML (Application/System/Security samples, an event with no PID, a Verbose event), unparseable XML falls back gracefully. |

## Architecture touch points

- **Threading:** `WinEventReader` does all work off the main thread and reaches
  the UI only via `batch_ready` / `error` / `stream_ended` — identical to
  `AdbReader`. Batching reuses `should_flush` so a burst of events can't flood the
  event loop.
- **Model/proxy:** none new. Events become `LogEntry` rows; all existing gates
  (level, tag, pid, exclude, device/source) apply. `source` distinguishes channels
  in a merged tab.
- **Dependency direction:** `ui → winlog → core`, matching `ui → adb → core`.
  `core/winevent.py` imports no Qt and no pywin32 (OS-free), preserving the rule
  that `core/` tests run headless on any OS.

## Risks & regressions to check

- **OS gating:** pywin32 must never be imported at module load; only inside
  `WinEventReader.run()`. On Linux/CI, selecting a Windows source should surface a
  friendly error, not crash. Verify the app still imports and all tests pass on CI.
- **Time filter interplay:** `since:`/`until:` parse the logcat time format; keep
  Windows timestamps in the same `"MM-DD HH:MM:SS.mmm"` shape so those tokens keep
  working. Note the missing year (logcat has none either).
- **Security channel** typically needs elevation; a subscribe failure must report
  cleanly (permission error → `error` signal), not hang.
- **Volume:** Security/System can be high-rate; confirm batching + the ring-buffer
  cap hold up (reuse the perf smoke approach).
- **Source selector:** generalizing the device bar must not regress adb device
  pick/refresh/Wi-Fi, remembered-serial, or merged view.
- **Start/stop/clear/pause, autoscroll-at-bottom, auto-reconnect** semantics for
  the new reader (reconnect likely N/A for Event Log — decide behavior).

## Verification

- [ ] `uv run pytest` (new `test_winevent.py`; existing suites green on Linux)
- [ ] `uv run ruff check .` and `uv run ruff format --check .`
- [ ] Smoke/screenshot via `run-zlog` for the source picker (channel listed)
- [ ] Manual on Windows: stream Application + System, filter by `level:`/`tag:`,
      confirm PID/provider populate; verify a graceful error on Linux.

## Open questions

- **Phasing:** land `core/winevent.py` + tests first (zero-risk, no UI), then the
  reader, then the source-selector UI? Leaning yes — it de-risks the mapping early.
- **EventID:** fold into the `tag` (`Provider/EventID`) or prefix the `message`?
  Leaning message prefix so tag-based filtering stays clean.
- **Channel list:** a curated fixed set vs. enumerating all channels via
  `wevtutil el` (hundreds). Leaning curated default + an "advanced: type a channel"
  entry.
- **Live vs. snapshot:** `EvtSubscribe` (live push) as the primary path; do we also
  want a "load last N events" snapshot mode (like logcat `-T`)? Probably yes, as a
  tail option.
- **pywin32 vs. stdlib:** `EvtSubscribe` needs pywin32. Is adding that Windows-only
  dependency acceptable, or prefer polling `wevtutil qe` (no dependency, laggier)?
