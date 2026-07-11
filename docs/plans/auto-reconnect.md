# Plan: Auto-reconnect on device drop

- **Status:** Done
- **Owner:** unassigned
- **Created:** 2026-07-11
- **Related:** ROADMAP v1.2 "Capture & scale" (last item), [device-picker.md](device-picker.md),
  [tail-count.md](tail-count.md)

## Goal

A capture survives a USB/wifi-adb hiccup: if the streaming device drops, zLog
notices, polls for it to come back, and resumes the stream **from where it left
off** — no manual Start, no re-dumping the whole on-device buffer.

## Why

Real Android debugging drops the adb connection constantly (cable jostle, doze,
wifi-adb). Today that silently ends the stream and the user must notice and press
Start. This is the "trustworthy on long captures" goal of v1.2.

## The duplication problem (and fix)

Restarting `adb logcat` re-emits the entire on-device ring buffer from the start,
duplicating everything already shown. Fix: track the newest log timestamp seen and
resume with `adb logcat -T '<time>'`, which prints from that time onward. A couple
of boundary lines may repeat; the whole buffer does not.

## Design

| File | Layer | Change |
|---|---|---|
| `src/zlog/adb/reader.py` | adb | Add a `stream_ended` signal, emitted at the end of `run()` only when the process ended without a `stop()` (`self._running` still True). Add a `since_time` param; `build_logcat_command` maps it to `-T <time>` (winning over the `-T <count>` tail). |
| `src/zlog/core/devices.py` | core | Pure `is_serial_streamable(devices, serial)` — target serial present & online, or (falsy serial) any online device. |
| `src/zlog/ui/main_window.py` | ui | Split `start()` into `start()` + `_start_reader(serial, since_time)`. Track intent (`_want_stream`), target (`_reconnect_serial`), and `_last_time` (updated in `on_batch`). A 2s `QTimer` drives `_try_reconnect`, which polls `list_devices()` and, once the device is streamable again, restarts via `_start_reader(..., since_time=_last_time)`. `stop()` clears intent + stops the timer. `_on_stream_ended` starts polling only if `_want_stream`. |

## Architecture touch points

- **Worker→UI via signals only:** the new `stream_ended` is a Qt signal delivered
  on the main thread; the timer/poll and restart all run on the main thread.
- **core stays Qt-free:** the device-availability decision is a pure function, unit
  tested; `list_devices()` (subprocess) stays in `adb/`.
- **No new settings:** always-on; only triggers on an unexpected end while intending
  to stream. A user Stop suppresses it.

## Risks & regressions to check

- **No duplication:** resume uses `-T <last time>`, not a fresh full stream.
- **User Stop must not reconnect:** `_want_stream=False` + timer stopped in `stop()`.
- **adb flakiness while polling:** `list_devices()` errors are swallowed so polling
  keeps retrying.
- **Default device (no serial):** reconnects when any online device appears.

## Verification

- [x] `uv run pytest` (166 passed; new: reader `-T <time>` argv, `is_serial_streamable`,
      `_last_time` tracking + reconnect resume, waits while absent, ignored after Stop)
- [x] `uv run ruff check .` and `uv run ruff format --check .`
- [ ] Manual: stream, unplug/replug the device, confirm it resumes near the last line.
