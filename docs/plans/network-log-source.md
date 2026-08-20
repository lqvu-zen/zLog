# Plan: Network log source (TCP listener)

- **Status:** Approved  <!-- Draft | Approved | In progress | Done | Abandoned -->
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
| `src/zlog/net/reader.py` (new package, sibling to `adb/`/`winlog/`) | net | `NetworkReader(QThread)`: `socket.socket(AF_INET, SOCK_STREAM)`, `bind`/`listen`, `accept()` on a timeout loop (like `FileFollower`'s poll, so `stop()` is bounded rather than blocking forever in `accept()`/`recv()`); reuses `core.tailer.split_complete_lines` for line framing and `parse_line` per line; same `batch_ready`/`error`/`stream_ended` signals, same `_BATCH_SIZE`/`_FLUSH_INTERVAL`/`should_flush` shape as `ui/file_follower.py` and `winlog/launcher.py`. |
| `src/zlog/core/tailer.py` | core | No change — `split_complete_lines` is already Qt-free and reused as-is. |
| `src/zlog/ui/network_dialog.py` (new) | ui | Small dialog: bind address (default `127.0.0.1`), port, Start button. Defaults to loopback; binding `0.0.0.0` requires an explicit, separately-labeled checkbox with a one-line warning (see Risks). |
| `src/zlog/ui/main_window.py` | ui | `listen_network()` slot mirroring `follow_file()`/`launch_app()`: opens the dialog, constructs `NetworkReader(host, port, formats=...)`, `self.capture.attach(sess, reader, stream_label=f"tcp:{port}")`. |
| `src/zlog/ui/menus.py` | ui | File-menu action "Listen on &Network…" next to "&Follow File…". |
| `src/zlog/core/settings.py` | core | Optional `"last_network_port": 0` in `DEFAULTS` to prefill the dialog next time (small; mirrors `last_launch`). |
| `tests/test_net_reader.py` (new) | — | Whatever is pure gets tested directly (line framing is already covered by `test_tailer.py`); a real socket accept loop is hard to unit test headlessly, so keep `NetworkReader` thin and push anything non-trivial into a pure helper first. |

## Architecture touch points

- **Threading:** same contract as every reader — `accept()`/`recv()` block on this
  thread only; the UI is reached only via `batch_ready`/`error`/`stream_ended`.
- **Model/proxy:** none.
- **Dependency direction:** `net/` sits beside `adb/`/`winlog/`, importing only
  `core/`; `ui` imports `net`, never the reverse.

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
- **Unbounded line length from a hostile or broken sender** (never sends `\n`) —
  cap the buffered partial-line size and drop/flag rather than growing memory
  without bound; no existing source has needed this guard, because files and adb
  both terminate lines reliably.

## Verification

- [ ] `uv run pytest` (line-framing reuse; whatever pure helpers this adds)
- [ ] `uv run ruff check .` / `ruff format --check .`
- [ ] Manual: a small script (or `nc localhost <port> < sample.log`) streams into
      a tab live; stopping the tab's capture releases the port so restarting
      works; a partial line held across two `send()` calls parses as one entry.
- [ ] Manual: attempting a second connection while one is active is rejected
      cleanly, not silently dropped.

## Open questions

- **TCP only, or UDP too?** TCP first (ordered, connection-oriented, matches
  every existing source's "one continuous stream" shape); UDP has no framing
  and no backpressure, and is a distinct enough shape to be its own follow-up if
  a real need shows up.
- **Should the listening port be remembered across launches** like `adb_path`?
  Leaning yes, low-cost.
