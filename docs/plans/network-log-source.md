# Plan: Network log source (TCP listener)

- **Status:** Done  <!-- Draft | Approved | In progress | Done | Abandoned -->
- **Owner:** unassigned
- **Created:** 2026-08-20
- **Related:** [file-follow.md](file-follow.md), [windows-debug-output.md](windows-debug-output.md), [merged-multi-device.md](merged-multi-device.md)

## Goal

Any process that can open a socket — a container, an embedded device, a remote
script, a service with no `adb`/Windows presence at all — can stream lines into a
zLog tab by connecting to a TCP port zLog listens on, with no file and no adb.

## Scope

- **In:** a `NetworkReader` that listens on a configurable `host:port`, accepts one
  connection at a time, frames newline-delimited text the same way every other
  source does, and feeds it through the existing `parse_line`/format machinery; a
  "Listen on &Network…" File-menu action + a small dialog (bind address, port);
  wired into `CaptureController` exactly like `FileFollower`.
- **Out (non-goals):** TLS, authentication, accepting multiple simultaneous
  senders into one tab (that shape already exists for devices via
  `merged-multi-device.md`; not revisited here), any framing/protocol beyond
  newline-delimited text (no syslog RFC 5424 parsing — a syslog sender's raw text
  just becomes the message, same as any unrecognized line today), UDP (a
  candidate follow-up, not v1).

## Design

| File | Layer | Change |
|---|---|---|
| `src/zlog/net/reader.py` (new package, sibling to `adb/`/`winlog/`) | net | `NetworkReader(QThread)`. **`select.select([server, conn], ...)` rather than a blocking `accept()`/`recv()` timeout loop** — the sketch's shape would only let one of "accept a new connection" / "read the active one" happen per cycle by polling each in turn; `select` multiplexes both, which is what makes the "reject a second sender immediately" behavior deterministic rather than racing the poll cadence (see Risks). Also emits a new `listening(port)` signal once bound, resolving `port=0` (any available port) to the real one — the sketch didn't anticipate an ephemeral port, but the dialog's "0 = choose one" needed *some* way to tell the user (and the tab label) what it picked. |
| `src/zlog/core/tailer.py` | core | No change — `split_complete_lines` reused as-is. |
| `src/zlog/ui/network_dialog.py` (new) | ui | Port field (blank/0 = ephemeral) + a checkbox for `0.0.0.0` (unchecked = loopback-only), rather than a free-text host field — a checkbox can't be mistyped into an unsafe bind, which a text field could. |
| `src/zlog/ui/main_window.py` | ui | `listen_network()` + `_on_network_listening(sess, port)` (updates the tab label/status once the real port is known, since binding happens on the reader's thread, not synchronously in the slot). |
| `src/zlog/ui/menus.py` | ui | File-menu action "Listen on &Network…" next to "&Follow File…". |
| `src/zlog/core/settings.py` | core | `"last_network_port": 0` added to `DEFAULTS`, plus the matching `_settings_specs()` entry in `main_window.py` (both are required — see `test_specs_cover_exactly_defaults`, which guards exactly this drift). |
| `tests/test_net_reader.py`, `tests/test_network_source.py` (new) | — | Real loopback-socket integration tests (fast, no external network): ephemeral-port resolution, streaming, a partial line split across two `send()`s, a second connection rejected while the first keeps working, reconnect-after-disconnect, bind failure, prompt stop; plus `NetworkDialog` validation and window wiring. |

## Architecture touch points

- **Threading:** same contract as every reader — `select`/`accept`/`recv` block
  on this thread only; the UI is reached only via
  `batch_ready`/`error`/`stream_ended`/`listening`.
- **Model/proxy:** none.
- **Dependency direction:** `net/` sits beside `adb/`/`winlog/`, importing only
  `core/`; `ui` imports `net`, never the reverse. Confirmed clean — `net/reader.py`
  imports nothing from `ui`.

## Risks & regressions to check

- **A dev tool that opens a listening socket by default is a real foot-gun.**
  Default bind is `127.0.0.1`; binding to all interfaces requires an explicit,
  separately-labeled opt-in with a warning shown in the dialog — never make
  `0.0.0.0` the default.
- **Unblocking `stop()`:** an indefinite blocking `accept()`/`recv()` would make
  `stop()` hang; use `settimeout()` and poll `self._running`, the same bound
  `FileFollower.stop()` already relies on (`self.wait(3000)`).
- **Port-in-use / bind failure** must reach the UI via the `error` signal, never
  raise out of `run()`.
- **One connection at a time, decided up front:** reject a second connection
  attempt while one is active (report via `error`) rather than silently queuing
  or merging — simplest, and matches `LaunchReader`'s "one child" model.
  **Implementation note:** `listen()`'s backlog is set to 5, not 1 — with a
  backlog of 1, two near-simultaneous connection attempts could have the *OS*
  refuse the second one outright (a bare connection-refused, no message) before
  our own accept-then-reject logic ever runs. A slightly larger backlog makes
  the accept-then-close-with-a-message path the one that actually fires,
  deterministically, which is what `test_second_connection_is_rejected_not_queued`
  pins.
- **Unbounded line length from a hostile or broken sender** (never sends `\n`) —
  cap the buffered partial-line size and drop/flag rather than growing memory
  without bound; no existing source has needed this guard, because files and adb
  both terminate lines reliably.

## Verification

- [x] `uv run pytest` — `tests/test_net_reader.py` (real loopback sockets: ephemeral
      port resolves, streams, partial-line-across-two-sends is one entry, second
      connection rejected while the first keeps working, reconnect after
      disconnect accepted, bind failure reports an error, prompt stop) and
      `tests/test_network_source.py` (`NetworkDialog` defaults/validation/remote
      checkbox; window wiring: reader starts, port resolves into the tab label,
      cancel starts nothing, `last_network_port` round-trips through settings) —
      all green.
- [x] `uv run ruff check .` / `ruff format --check .` clean.
- [x] Manual (`run-zlog` `listen-network` scenario, screenshotted): a real socket
      client connects to a real ephemeral-port listener and its lines stream into
      the tab correctly (`tcp:51537` in the captured run).
- [x] Covered by `test_second_connection_is_rejected_not_queued`: opening a
      second real socket connection while the first is active gets an `error`
      signal containing "Rejected", and the first connection's traffic keeps
      flowing afterward — done as an automated test against real sockets, not
      only by hand.

## Open questions

- **TCP only, or UDP too?** TCP first (ordered, connection-oriented, matches
  every existing source's "one continuous stream" shape); UDP has no framing
  and no backpressure, and is a distinct enough shape to be its own follow-up if
  a real need shows up. Unchanged by this pass.
- **Should the listening port be remembered across launches** like `adb_path`?
  **Resolved: yes** — `last_network_port` in settings, prefilling
  `NetworkDialog`'s port field next time (0 still means "choose one").
