# Plan: Merged multi-device view

- **Status:** Draft  <!-- Draft | Approved | In progress | Done | Abandoned -->
- **Owner:** unassigned
- **Created:** 2026-07-20
- **Related:** [device-tabs.md](device-tabs.md), [new-window.md](new-window.md), [process-name-column.md](process-name-column.md)

## Goal

One log view that merges the streams from several connected devices/emulators at
once, each line tagged by its source device, so you can watch a phone + wear + an
emulator (or a phone + its paired device) interleaved in a single timeline.

## Scope

- **In:** a "Merged" mode that starts a reader per selected device into one shared
  model; each entry annotated with its device serial; a device column/tint to tell
  sources apart; a `device:<serial>` query filter; Start/Stop covers all readers.
- **Out (non-goals):** cross-device clock alignment/skew correction (devices aren't
  time-synced — order by arrival, show each device's own timestamp); reconnect
  choreography per device beyond the existing single-device logic in phase 1.

## Design

Today each tab is a `LogSession` with one `AdbReader` → one model
(`device-tabs.md`, `new-window.md`). Merged mode reuses that plumbing but fans
several readers into a *single* model, tagging entries with their serial. The tag
must ride on `LogEntry` without breaking the Qt-free parser, so it's attached at
the UI boundary, not in `core.parser`.

| File | Layer | Change |
|---|---|---|
| `src/zlog/core/models.py` | core | Add an optional `source: str = ""` field to `LogEntry` (frozen dataclass, default keeps every existing construction/parse call working). The parser doesn't set it; the merged reader does. |
| `src/zlog/adb/reader.py` | adb | `AdbReader` gains an optional `source` label; when set, stamp each parsed `LogEntry` with it (via `dataclasses.replace`) before batching. Single-device streams leave it "". |
| `src/zlog/ui/log_model.py` | ui | A `SOURCE_ROLE` (and, when merged, show the device in the process/40-col area or a dedicated tint). Proxy gains a `device:` gate (`set_devices(set|None)`) mirroring the pid gate. |
| `src/zlog/core/query.py` | core | Parse a `device:<serial>` token (and `-device:`), added to `QuerySpec`; classify it for the token highlighter + chips. |
| `src/zlog/ui/main_window.py` | ui | A "Merged view" entry (device bar or File menu): pick devices (multi-select), start an `AdbReader(source=serial)` per device into the active session's one model; Stop stops all; the device column/tint shows the source; the `device:` filter and a per-device color legend. Follow/pause/clear operate on the merged model unchanged. |
| `tests/` | — | `LogEntry.source` default + `replace` stamping; parser still returns `source=""`; proxy `device:` gate; query parses `device:`; a main-window smoke feeding two fake readers into one model. |

## Architecture touch points

- **Threading:** N `AdbReader` `QThread`s, each reaching the UI only via its
  `batch_ready` signal into the *same* `append_entries` slot — the core rule holds;
  appends are serialized on the main thread. Stop must join all readers.
- **Model/proxy:** one virtualized model fed by many readers; a new read role +
  one new proxy gate. No per-row widgets.
- **Dependency direction:** `source` lives on the core `LogEntry` but is *set* in
  `adb`/`ui`; `core.parser` stays untouched. `ui → adb → core` holds.

## Risks & regressions to check

- Ordering: interleave by arrival (append order), not by timestamp — devices'
  clocks differ. Document this so users don't read cross-device order as causal.
- Backpressure: several busy devices multiply the line rate; the reader coalescing
  (`should_flush`) and ring-buffer cap must hold up — exercise with the perf harness
  extended to multi-source.
- PID/process-name collisions across devices (same PID on two phones): the process
  map must be keyed by `(source, pid)` in merged mode, or names will cross-wire.
- `LogEntry` gaining a field: audit every constructor/`replace`/serialization
  (`session.format_entry`, exports, bundle) so nothing positionally breaks.
- Stop/reconnect with N readers: ensure all threads terminate; a single device drop
  shouldn't kill the merged view.

## Verification

- [ ] `uv run pytest` (LogEntry.source; parser unaffected; proxy device gate; query
      device token; two-reader merge smoke)
- [ ] `uv run ruff check .` and `uv run ruff format --check .`
- [ ] `run-zlog` scenario `merged-devices`: feed two labeled sources, screenshot the
      tagged, interleaved view; assert `device:` filters to one.

## Open questions

- Source display: a dedicated device column, or fold the serial into the existing
  process column / a per-device row tint? Leaning a short device tint + `device:`
  filter to avoid widening the metadata columns.
- Scope of phase 1: is per-device reconnect needed on day one, or is "stop all /
  restart" acceptable initially? Leaning the simpler stop/restart first.
