# Plan: Redaction on export

- **Status:** Done
- **Owner:** unassigned
- **Created:** 2026-07-16
- **Related:** ROADMAP "Export & sharing" (P2), [export-formats.md](export-formats.md),
  [save-load.md](save-load.md), [save-filtered.md](save-filtered.md)

## Goal

After this ships, an opt-in **Redact on export/save** toggle masks common
secrets — email addresses, IP addresses, and long token-like strings — in the
message text of every line written to disk (Save Log, Save Visible, and the
CSV/JSON/HTML exports), so a log can be shared without leaking PII/credentials.

## Scope

- **In:** a Qt-free `core/redact.py` with a fixed regex set (email, IPv4, and
  bearer/hex/base64-ish tokens ≥ 20 chars) that replaces matches with a masking
  placeholder; a persisted **Redact on export** toggle (View menu, checkable);
  redaction applied to Save Log, Save Visible, and File → Export CSV/JSON/HTML
  when the toggle is on.
- **Out (non-goals):** redacting the live on-screen view (this is export-only),
  configurable/custom redaction patterns, redacting tag/pid/time fields (only
  the message carries free-form secrets), clipboard-copy redaction (a separate
  item if wanted), reversible/keyed redaction.

## Design

| File | Layer | Change |
|---|---|---|
| `src/zlog/core/redact.py` (new) | core | `redact_text(s: str) -> str` — applies each pattern in a fixed list, replacing matches with a per-kind placeholder (`[email]`, `[ip]`, `[token]`). `redact_entry(entry: LogEntry) -> LogEntry` — returns a copy (`dataclasses.replace`) with `message = redact_text(entry.message)`; other fields untouched. `redact_entries(entries) -> list[LogEntry]`. Order patterns so the broad token rule runs last and doesn't clobber the more specific email/ip masks (e.g. mask email and ip first, token last, or make the token rule exclude already-masked text). Pure, no Qt, unit-tested. |
| `src/zlog/core/settings.py` | core | Add `"redact_on_export": False` to `DEFAULTS`. |
| `src/zlog/ui/main_window.py` | ui | New checkable `self.redact_action` ("Redact on Export", built next to `autosave_action`/`collapse_action` at line ~700). A helper `_maybe_redact(entries)` returns `redact_entries(entries)` when the toggle is checked, else the list unchanged. Route the three write paths through it: `_write_log` (used by Save Log + Save Visible, line 2082), and `_export` (line 2105) — apply just before `entries_to_text(...)` / `formatter(...)`. Add `redact_action` to the View menu (near the collapse/process toggles) and to `_settings_specs()` as `("redact_on_export", self.redact_action.isChecked, lambda v: self.redact_action.setChecked(bool(v)))`. Status-bar messages note when a save was redacted. |
| `tests/test_redact.py` (new) | tests | `redact_text` masks an email, an IPv4, and a long token; leaves ordinary text and short numbers (pids, small ints) alone; `redact_entry` only touches `.message` and returns a new `LogEntry` (original unchanged). |
| `tests/test_main_window_settings.py` | tests | `redact_on_export` is covered by the existing `test_specs_cover_exactly_defaults` guard automatically; add a round-trip assert that toggling it and applying an export path produces masked output (or keep it at the core level if wiring a full export in a test is heavy). |

## Architecture touch points

- **Qt-free core:** all masking lives in `core/redact.py`, directly unit-tested
  without a display — same shape as `core/export.py` (pure string in/out).
- **Export-path only, non-destructive:** redaction transforms a *copy* of the
  entries at write time (`dataclasses.replace` on the frozen `LogEntry`); the
  master list and the on-screen view are never mutated, so nothing is lost and
  the toggle has no effect on filtering/reading.
- **Persistence via `_settings_specs()`** — one more `(key, get, set)` row, so
  it can't drift from how every other toggle persists; the coverage guard
  enforces the new `DEFAULTS` key has a spec.
- **Dependency direction (`ui → core`)** holds: `main_window` imports
  `core.redact`; core imports nothing new.

## Risks & regressions to check

- **Over-masking:** the token rule (long hex/base64) must not eat ordinary long
  words or file paths; keep it conservative (require a minimum length and a mix
  of char classes) and cover the false-positive cases in tests.
- **Under-masking:** an email inside a URL or an IP with a port should still be
  caught; test a couple of embedded cases.
- **Pattern ordering:** masking must be idempotent and order-independent enough
  that placeholders from one rule aren't re-matched/mangled by a later rule
  (test running redact_text twice == once).
- **Every write path covered:** Save Log, Save Visible, and all three exports
  must honor the toggle; the session/.zsession bundle is **out of scope**
  (it's a reload-fidelity format, not a share format) — confirm we deliberately
  don't redact it and note that.

## Implementation notes

- Surfaced as a checkable **"Redact secrets"** item at the top of the
  **File → Export** submenu (more discoverable than a View toggle, right where
  you export). Applies to Save Log, Save Visible, and CSV/JSON/HTML export via a
  shared `_maybe_redact` helper; status-bar messages append "(redacted)".
- The `.zsession` bundle is deliberately **not** redacted — it's a
  reload-fidelity format, not a share format.

## Verification

- [x] `uv run pytest` (all green; 1 pre-existing unrelated timing flake)
- [x] `uv run ruff check .` and `uv run ruff format --check .`
- [x] Screenshot skipped by design (the feature is a menu checkbox + file
      output); redaction verified at the unit level
- [x] Manual: covered by `tests/test_redact.py` (email/ip/token masking,
      false-positive guards, idempotence, non-destructive copy) and
      `tests/test_main_window_settings.py::test_redact_toggle_drives_maybe_redact`
      (toggle drives the write-path helper)

## Open questions

- **Placeholder style:** `[email]`/`[ip]`/`[token]` chosen for readability;
  flag in review if a fixed-width mask (`***`) is preferred.
