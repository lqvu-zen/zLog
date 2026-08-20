# Plan: Webhook notification on a watch-pattern hit

- **Status:** Approved  <!-- Draft | Approved | In progress | Done | Abandoned -->
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
| `src/zlog/core/webhook.py` (new) | core | `build_payload(entry, template) -> dict`: same placeholder substitution as `core/watch_action.py::expand_command`, but templating into a JSON-serializable dict/string body rather than an argv list. Pure, unit-tested — no network code here. |
| `src/zlog/ui/webhook_sender.py` (new) | ui | A `QRunnable` (via `QThreadPool`) or a small dedicated `QThread` that POSTs the built payload using `urllib.request` — **must not run inline on the UI thread**, since a slow/unreachable endpoint would otherwise freeze the whole window during a watch hit (see Risks). Logs success/failure to `core.applog`, no UI feedback beyond that (best-effort, like the existing beep/command). |
| `src/zlog/ui/watch_dialog.py` | ui | New "Webhook URL" field alongside `pattern_edit`/`command_edit`; `get_values()` returns the triple. |
| `src/zlog/ui/main_window.py` | ui | `self._watch_webhook = ""`; a `_webhook_last` throttle var mirroring `_watch_cmd_last` (`main_window.py:204`); `_run_watch_webhook(entry)` mirroring `_run_watch_command` (`main_window.py:1842`), fired alongside it at `main_window.py:3585`. |
| `src/zlog/core/settings.py` | core | `"watch_webhook": ""` in `DEFAULTS`, saved/loaded like `watch_command`. |
| `tests/test_webhook.py` (new) | — | `build_payload`: all placeholders substituted, unknown placeholder left literal (matches `expand_command`'s documented behavior), blank template → no-op. |

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

- [ ] `uv run pytest` (`build_payload` cases above)
- [ ] `uv run ruff check .` / `ruff format --check .`
- [ ] Manual: point at a real endpoint (a local test server, or
      `https://httpbin.org/post`) and confirm delivery of a real hit.
- [ ] Manual: point at an unreachable/slow endpoint and confirm the UI does not
      freeze during a hit.
- [ ] Manual: a burst of matching lines fires at most one webhook per throttle
      window, matching the existing command throttle's behavior.

## Open questions

- **JSON POST only, or also a simple templated-URL GET** for services that want
  that shape? Leaning POST-only for v1 — simplest, covers Slack/generic
  receivers.
- **Worth adding HMAC signing** (a shared secret + signature header) for
  receivers that verify authenticity? Defer until a concrete receiver needs it.
- **Any UI feedback on delivery failure**, or log-only? Leaning log-only —
  matches this being a best-effort notification, not a critical path.
