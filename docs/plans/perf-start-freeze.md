# Plan: Fix UI freeze when starting a stream on a busy device

- **Status:** Done
- **Owner:** unassigned
- **Created:** 2026-07-14

## Problem

On **Start**, `adb logcat` dumps the whole on-device buffer fast, arriving as
thousands of 50-line batches. Two per-batch UI operations made this a freeze:
`_update_counts` (wired to 5 model/proxy signals) called `proxy.level_counts()`,
which walks every visible row — O(visible) per batch → **O(n²)** when a filter is
active; and `scrollToBottom()` ran on every batch (thousands of layout passes).

## Fix

Coalesce both, mirroring the existing debounced heat-mark recompute:

- **Debounce `_update_counts`**: route the row signals to `_schedule_counts`, which
  starts a single-shot 150 ms timer; the recompute runs at most ~7×/sec.
- **Coalesce the follow auto-scroll**: `_on_batch` starts an 80 ms single-shot timer
  instead of scrolling per batch, and cancels it when the user has scrolled up (so
  the "never yank" guarantee holds).

## Verification

- [x] `uv run pytest` (261) incl. the coalesced-scroll follow test + a counts-debounce test.
- [x] ruff clean.
- [x] Bench: 100k lines / 2000 batches with a filter active → 0.22 s (was multi-minute).

## Update (2026-07-14) — real root cause

The debounce alone didn't fix it: the freeze was the **reader flooding the event
loop** with a cross-thread `batch_ready` signal every 50 lines during the initial
buffer dump (thousands of queued signals → the loop can't repaint → "Not
Responding"). Fixes:
- **Reader coalescing**: emit at most every `_BATCH_SIZE=2000` lines OR every
  `_FLUSH_INTERVAL=0.1s` (pure `should_flush`, unit-tested). ~40x fewer signals on a
  300k-line dump; live-tail latency stays ~100ms. Windows-safe (no select on pipes).
- **Default Start = last 10,000 lines** (`tail_count` default 0 → 10000; new "Last
  10,000" option) so a giant device buffer never floods at all. Existing saved
  settings keep their choice — pick Settings → Capture → Start from to change it.
