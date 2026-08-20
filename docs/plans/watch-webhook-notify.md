# Plan: Webhook notification on a watch-pattern hit

- **Status:** Done  <!-- Draft | Approved | In progress | Done | Abandoned -->
- **Owner:** unassigned
- **Created:** 2026-08-20
- **Related:** [watch-pattern.md](watch-pattern.md), [watch-run-command.md](watch-run-command.md)

## Goal

Notify an external service (Slack, a generic webhook receiver, PagerDuty's
generic webhook, etc.) with a JSON POST when a captured line matches the watch
pattern — off the UI thread, without relying on the user having `curl` installed
and without putting a secret webhook URL in a visible process command line.

## Read this first: the existing "Run command" can already sort of do this

`watch-run-command.md` already lets the command template be
`curl -X POST -d {message} https://hooks.example.com/...`, so a webhook post is
technically already possible today via `core/watch_action.py::expand_command`.
Two things make a dedicated feature worth it anyway:

1. **The webhook URL becomes visible in the process list** (`ps`/Task Manager)
   every time it fires, on a shared machine that's a real secret-exposure risk a
   curl-argv approach can't avoid.
2. **It requires `curl` on PATH** — this plan uses Python's stdlib HTTP client
   instead, so it works everywhere zLog already runs.

## Scope

- **In:** a "Webhook URL" field in `WatchDialog`, separate from "Run command";
  a JSON POST of the same placeholder values `expand_command` already supports
  (`{message} {tag} {pid} {level} {time} {line}`), fired off the UI thread; the
  same hit-throttling `_run_watch_command` already applies.
- **Out (non-goals):** retries/backoff, delivery-confirmation UI, HMAC/request
  signing (flagged as an open question), configurable headers/auth beyond a
  bare JSON POST to one URL.

## Design

| File | Layer | Change |
|---|---|---|
| `src/zlog/core/webhook.py` (new) | core | **`build_payload(entry) -> dict`, no `template` parameter** — the sketch's "template" concept (a user-authored JSON body shape) was dropped: the payload is a fixed shape (`message`/`tag`/`pid`/`level`/`time`/`line`, the same field set `expand_command` exposes), which is simpler, has no injection surface to reason about (proper `json.dumps`, not string substitution into a body), and is still generically useful — any receiver can pick the fields it wants from a fixed object. A per-URL custom body template is a candidate follow-up, not v1. |
| `src/zlog/ui/webhook_sender.py` (new) | ui | `_WebhookWorker(QObject, QRunnable)` run via `QThreadPool.globalInstance()`, POSTing with `urllib.request`; its `finished(success, message)` signal is a normal Qt cross-thread connection back to `MainWindow` (safe because `MainWindow` lives on the thread with the real, running event loop — unlike the DirFollower situation in `directory-glob-follow.md`, where the *receiver* had no event loop). |
| `src/zlog/ui/watch_dialog.py` | ui | New "Webhook URL" field alongside `pattern_edit`/`command_edit`; `get_values()` returns the triple; hint text updated to disclose the plaintext-storage posture (see Risks). |
| `src/zlog/ui/main_window.py` | ui | `self._watch_webhook = ""`, `self._webhook_last = 0.0`, `self._webhook_pending = False`; `_run_watch_webhook(entry)` / `_on_webhook_done(success, message)`; `_apply_watch`/`_set_watch_dialog` extended with the same "confirm before enabling" flow the command field already has (a webhook sends log content to an external URL, which deserves the same explicit opt-in as running an arbitrary command). |
| `src/zlog/core/settings.py` | core | `"watch_webhook": ""` in `DEFAULTS`, plus the matching `_settings_specs()` entry (both required — `test_specs_cover_exactly_defaults` guards this exact drift). |
| `tests/test_webhook.py`, `tests/test_webhook_sender.py` (new) | — | `build_payload` field mapping + JSON-serializability; `send_webhook` against a **real local `http.server`** (loopback, ephemeral port) — POST delivered with the right body/content-type, and an unreachable endpoint reports failure without blocking; plus window-wiring tests (throttle, in-flight bound, confirm-before-enabling dialog flow). |

## Architecture touch points

- **Threading:** the network call is the one part of this plan that must never
  touch the UI thread — same rule that governs every reader in this codebase,
  applied here to a one-shot outbound call instead of a long-lived stream.
- **Model/proxy:** none.
- **Dependency direction:** `core/webhook.py` stays Qt-free (payload building
  only); the actual HTTP call and its off-thread dispatch are `ui`-only.

## Risks & regressions to check

- **Must never block the UI thread.** A synchronous `urlopen()` call inline in
  `_run_watch_webhook` would freeze the window for the duration of a slow or
  timed-out request — exactly the kind of bug this codebase's "workers never
  touch widgets, work happens off-thread" rule exists to prevent, applied here
  to a network call instead of a reader loop.
- **The webhook URL is a secret** (Slack incoming-webhook URLs are
  bearer-equivalent). It must not be written to `zlog.log` on error — log only
  the host, or a redacted form, never the full URL with its token path. Note it
  will still sit in plaintext in `settings.json`, same posture as `adb_path`/
  `mapping_path` today — acceptable precedent, but call it out in the dialog's
  hint text so it isn't a silent surprise.
- **Must reuse the existing throttle, not invent a new cadence** — a burst of
  matching lines must not flood the endpoint; `_run_watch_command`'s throttle
  pattern already solves this and should be copied exactly, not redesigned.
- **A slow/unreachable endpoint must not pile up outstanding requests** if hits
  keep arriving — bound in-flight requests (e.g. skip firing if the previous
  request from this session hasn't completed) rather than letting them queue
  unbounded on a bad endpoint.

## Verification

- [x] `uv run pytest` — `tests/test_webhook.py` (payload fields, JSON
      serializability), `tests/test_webhook_sender.py` (real local
      `http.server`: POST delivered with correct body/headers, unreachable
      endpoint reports failure), and the window-wiring tests in
      `tests/test_main_window_settings.py` (throttle, in-flight bound,
      no-URL no-op, `_apply_watch` webhook-preserved-when-not-passed,
      confirm/decline dialog flow) — all green.
- [x] `uv run ruff check .` / `ruff format --check .` clean.
- [x] Manual (`run-zlog` `watch-webhook` scenario, screenshotted): the dialog
      renders all three fields (pattern/command/webhook) with the disclosure
      hint.
- [x] Covered by `test_send_webhook_unreachable_reports_failure_without_blocking`:
      a real dead endpoint (a port bound then released, so nothing accepts on
      it) reports failure promptly via the callback rather than hanging — done
      as an automated test against a real socket condition, not only "seemed
      fine by hand."
- [x] Covered by `test_run_watch_webhook_sends_and_throttles` and
      `test_run_watch_webhook_bounds_in_flight_requests`: a second hit within
      the throttle window, and a second hit while a request is still
      in-flight, both fire at most once.

## Open questions

- **JSON POST only, or also a simple templated-URL GET** for services that want
  that shape? Leaning POST-only for v1 — simplest, covers Slack/generic
  receivers. Unchanged by this pass.
- **Worth adding HMAC signing** (a shared secret + signature header) for
  receivers that verify authenticity? Defer until a concrete receiver needs it.
- **Any UI feedback on delivery failure**, or log-only? **Resolved: log-only**,
  as leaned — `_on_webhook_done` writes to `zlog.log` via the module logger,
  no status-bar/toast, matching the beep/command's best-effort posture.
- **A per-URL custom JSON body template** (the original `build_payload(entry,
  template)` sketch) — worth adding if a real receiver needs a body shape the
  fixed field set can't satisfy. Not needed yet; the fixed shape covers every
  receiver considered so far.
