# Plan: ETW real-time tracing (bigger bet)

- **Status:** Abandoned — too risky for the payoff right now; revisit if a real
  need for it shows up (see note below)
  <!-- Draft | Approved | In progress | Done | Abandoned -->
- **Owner:** unassigned
- **Created:** 2026-07-24
- **Related:** [windows-event-log.md](windows-event-log.md), [windows-debug-output.md](windows-debug-output.md)

## Goal

Subscribe to Event Tracing for Windows (ETW) providers and stream their events
into zLog, so you can trace an app at the level Windows itself instruments —
beyond what `OutputDebugString` or the Event Log expose.

## Why (and why it's last)

ETW is the most powerful Windows tracing mechanism: high-frequency, structured,
and what modern .NET (`EventSource`) and many Microsoft components emit. But it's
also by far the biggest build here — sessions must be created and torn down as OS
resources, providers are identified by GUID, payloads are schema-driven, and
volume can be enormous. **Ship the cheaper sources first**; this one earns its
keep only if the others prove insufficient.

## Scope

- **In:** start a real-time ETW session for one or more provider GUIDs, decode
  events to `LogEntry`, stream into a tab, stop cleanly (no leaked session).
- **Out (non-goals):** kernel-flag tracing (stack walks, disk/network profiling),
  `.etl` file capture and replay, provider discovery UI beyond a typed GUID/name,
  and anything requiring a driver.

## Design

Two viable routes; the plan assumes (A) and treats (B) as the fallback.

**(A) In-process via pywin32/`ctypes`** — call `StartTrace`/`EnableTraceEx2`/
`ProcessTrace`. Full control and a genuine live stream, but a lot of struct
marshalling and easy to leak a session if teardown is wrong.

**(B) Shell out to a bundled tracer** — drive Microsoft's `tracelog`/`wpr`, or
`logman`, writing to a file we then follow with the tailer from
[file-follow.md](file-follow.md). Far less code, reuses machinery we'd already
have, but depends on external tools and adds latency.

| File | Layer | Change |
|---|---|---|
| `src/zlog/core/etw.py` (new) | core | Pure decoding/mapping: provider GUID validation, `map_etw_level(n)` (ETW levels 1–5 → F/E/W/I/V), and `event_to_entry(dict) -> LogEntry` given an already-decoded event dict. OS-free and unit-tested. |
| `src/zlog/winlog/etw_reader.py` (new) | winlog | `EtwReader(QThread)` with the standard `batch_ready`/`error` contract; owns the session lifecycle (start → process → stop), lazily importing the Windows bits. **Must** stop the session in a `finally`, and on startup clean up a stale session left by a crash (same fixed session name). |
| `src/zlog/ui/etw_dialog.py` (new) | ui | Pick provider(s) by GUID or well-known name, choose level and keywords. |
| `src/zlog/ui/main_window.py` | ui | Menu entry → dialog → `capture.attach(...)` in a tab, as with the other sources. |
| `tests/test_etw.py` (new) | — | Pure mapping/validation only; the session itself is manual-tested on Windows. |

## Architecture touch points

- **Threading:** `ProcessTrace` blocks — it must own the thread and be woken on
  stop by closing the trace handle; a naive flag check will hang the app on quit.
- **Model/proxy:** none new, but see the volume risk — ETW can outpace the UI far
  more than logcat does.
- **Dependency direction:** unchanged (`ui → winlog → core`), decoding stays pure.

## Risks & regressions to check

- **Leaked sessions** are the classic ETW bug: a crashed or improperly stopped
  session persists in the OS and blocks the next start. Use a fixed session name
  and delete any stale one at startup.
- **Elevation:** real-time sessions generally require administrator.
- **Volume:** a chatty provider can emit tens of thousands of events/second —
  batching plus the ring cap may not be enough; consider a hard rate limit and a
  visible "dropped N events" indicator.
- **Blocking teardown** (see threading) — verify the app quits promptly mid-trace.
- **Payload decoding** varies by provider; unknown schemas must degrade to a raw
  string rather than raising.

## Verification

- [ ] `uv run pytest` (pure mapping tests; suite green on Linux)
- [ ] `uv run ruff check .` and `uv run ruff format --check .`
- [ ] Manual on Windows (elevated): trace a known provider, confirm events arrive
      and Stop leaves **no** session behind (`logman query -ets` is empty of ours).

## Open questions

- **(A) or (B)?** Decide before any code — they share almost nothing. Leaning (B)
  first as a spike to prove the value, then (A) if it's worth the depth.
- Is this wanted at all, or do the debug-output + Event Log + file-follow sources
  already cover the real debugging need? **Revisit only after those ship.**
- Elevation UX: detect and tell the user, or attempt to relaunch elevated?
  Leaning detect-and-explain.

## 2026-07-30 update: abandoned

Decided the risk/payoff isn't there right now: leaked OS sessions if teardown
goes wrong, a blocking `ProcessTrace` call that can hang shutdown if woken
incorrectly, mandatory elevation, and volume far beyond what the logcat-tuned
batching was built for — on top of `ctypes` struct marshalling being the
fiddliest code in the app if route (A) is taken. The debug-output, Event Log,
and file-follow sources shipped since this plan was written and likely cover
most of the real debugging need already, which was this plan's own open
question. Restart from here (the design/risk analysis above still stands) if a
concrete case comes up that those three genuinely can't handle.
