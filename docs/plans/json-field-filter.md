# Plan: JSON auto-fields + a `field:` query token

- **Status:** Done — **scope cut at implementation time; see "What actually
  shipped" below** <!-- Draft | Approved | In progress | Done | Abandoned -->
- **Owner:** unassigned
- **Created:** 2026-08-20
- **Related:** [regex-extract-columns.md](regex-extract-columns.md), [tag-summary.md](tag-summary.md)

## What actually shipped (read this first)

This plan's own "Open questions" said it explicitly: **"This plan should not
proceed past Draft without confirming there's a real workload where the
summary-dialog flow is insufficient."** No such workload was ever confirmed —
there was no user request driving this specifically, just a brainstormed
candidate. Rather than build the risky half (the `field:` proxy filter + its
required per-row cache) on spec, this pass shipped only the cheap, unambiguously
useful half and left the expensive half undone:

- **Shipped:** JSON auto-detection (`core/extract.py::extract_json`), merged
  into the same `extract_fields()`/detail-pane path `regex-extract-columns.md`
  already built (its option (a) — the "smallest, fits the current delegate"
  choice that plan already made). A "View → Auto-detect JSON Fields" toggle
  turns it on; extracted keys (JSON's or regex's) show in the detail pane.
- **Not shipped:** the `field.<name>:<value>` query token, the `QuerySpec.fields`
  addition, and the `LogFilterProxy` gate + per-row extraction cache the Design
  table below sketches. Building that well requires the cache-invalidation-on-
  ring-buffer-eviction correctness the Risks section flags as "the regression
  most likely to slip through review" — real complexity to take on without a
  confirmed need for it. **This is the resolution to the plan's own open
  question**, not an oversight — see Open questions below for what would justify
  revisiting it.

The rest of this document is kept as originally written (including the
now-**not-implemented** filter design), since it's still the right reference if
someone later has a concrete case for the `field:` token.

## Goal

A line whose message is (or contains) a JSON object gets its keys parsed into
named fields with **no user regex**. (The second half of the original goal —
making any such field filterable via a new `field.<name>:<value>` query token,
closing the gap [regex-extract-columns.md](regex-extract-columns.md)
deliberately shipped without — was not built this pass; see above.)

## Scope

- **In (shipped):** a JSON auto-extractor in `core/extract.py`; a toggle to
  enable it alongside the existing regex-extractor list, surfaced through the
  same `extract_fields()`/detail-pane path as regex extraction.
- **Out (not shipped this pass — see above):** the `field.<name>:<value>`
  query token and its proxy filter gate.
- **Out (non-goals, unchanged):** typed comparisons (`>`, `<`, ranges) — string-
  substring only, matching the rest of the query language; nested JSON beyond
  one flatten level; turning extracted fields into sortable inline columns
  (still no column model, per the parent plan's decision).

## Design

### As implemented

| File | Layer | Change |
|---|---|---|
| `src/zlog/core/extract.py` | core | `extract_json(message) -> dict[str, str]`: try `json.loads` on the whole (stripped) message, else the first balanced `{...}` substring found via a linear brace-counting scan (no backtracking); flatten nested objects one level (`"a.b"` keys); `bool`/`None` stringified as `"true"`/`"false"`/`"null"`; a bare non-object JSON value (array/number/string) or anything malformed returns `{}` — never raises. |
| `src/zlog/ui/log_model.py` | ui | `LogTableModel` (not the proxy — no filtering, see below) gains `_json_autodetect` + `set_json_autodetect(bool)` and a private `_extract_all(message)` merging regex (`extract()`) and, if enabled, JSON fields (regex wins a name collision — it's the deliberate, user-authored one). Both `EXTRACT_ROLE`'s `data()` branch and the public `extract_fields(source_row)` route through it, so the detail pane picks up JSON fields for free. |
| `src/zlog/ui/main_window.py` | ui | `json_autodetect_action` (checkable `QAction`, View menu) wired the same way `fold_action` is: `toggled` → `_on_json_autodetect_toggled` (pushes into the model, refreshes the detail pane); the settings-spec getter reads `json_autodetect_action.isChecked` directly, no separate mirrored window attribute (matching `fold_traces`'s existing pattern, not `extract_patterns`'s). |
| `src/zlog/core/settings.py` | core | `"json_autodetect": False` in `DEFAULTS`. |
| `tests/test_extract.py` | — | `extract_json`: whole-message object, embedded-in-text, one-level flatten, `null`/`bool`, malformed/empty, non-object JSON, pathological input (many braces) never raises. |
| `tests/test_log_model.py` | — | `extract_fields()` combining regex + JSON with a name collision, JSON-only, auto-detect off by default, out-of-range row. |
| `tests/test_main_window_settings.py` | — | Toggling the action updates the detail pane live; `json_autodetect` round-trips through settings. |

### As originally sketched, not built (kept for reference)

| File | Layer | Change |
|---|---|---|
| `src/zlog/core/query.py` | core | `QuerySpec` gains `fields: tuple[tuple[str, str], ...]` (name, value-substring pairs); `field.<name>:<value>` tokens parsed like `tag:`/`proc:`; `_classify`/`token_spans` gain a `"field"` kind for query-bar highlighting. |
| `src/zlog/ui/log_model.py` | ui | `LogFilterProxy` reads `spec.fields`; `filterAcceptsRow` calls into `extract_fields(source_row)` to test each requested field. Needs a per-row cache, not a live extract on every filter pass — see Risks. |
| `tests/test_query.py` | — | `field.name:value` parses into `QuerySpec.fields`; `token_spans` classifies it. |

## Architecture touch points

- **Model/proxy:** a new filter predicate. This is the one place the design
  needs care (see Risks) — every other proxy gate reads a plain `LogEntry`
  attribute; this one requires running an extractor over the message first.
- **Dependency direction:** `core/extract.py` and `core/query.py` stay Qt-free;
  the proxy wiring is `ui`-only.
- **Threading:** none.

## Risks & regressions to check

**The first three items below (the cache, its ring-buffer interaction, and the
perf risk) are about the `field:` filter gate that was not built this pass —
kept here as reference for whoever picks that up.** The last two items are
about what actually shipped and were verified.

- **The central risk: `filterAcceptsRow` runs for every source row on every
  filter invalidation.** `regex-extract-columns.md` kept extraction lazy
  (per-visible-row only, via `EXTRACT_ROLE`) specifically to avoid this cost.
  Turning it into a filter gate means extracting on rows well outside the
  viewport — on a large capture this is a real, visible perf regression if done
  naively.
  - **Mitigation:** cache extracted fields per source row (a `dict[int, dict]`
    on the model), computed once and reused by both `EXTRACT_ROLE` and the new
    filter gate; invalidate the whole cache on `set_extractors`/
    `set_json_autodetect` (patterns changed) — the same pattern the model
    already uses for `_bookmarks`.
  - **Don't forget the ring-buffer eviction case:** `_trim_overflow`
    (`log_model.py:253`) already re-keys `_bookmarks` by subtracting the
    evicted count (`log_model.py:271-273`) when the cap trims old rows — the new
    extract cache needs the identical re-keying, or field filters will silently
    apply to the wrong rows after a trim. This is the one regression most likely
    to slip through review because it's invisible until `max_rows` is actually
    hit.
- **Catastrophic-backtracking risk is unchanged** from the parent plan — JSON
  parsing has no backtracking, but `json.loads` on a huge message on every row
  is itself the cost the cache above exists to bound. **Not a live concern
  today**, since nothing calls `extract_json` per-row during filtering — only
  lazily, for the one selected row shown in the detail pane.
- **Invalid/absent JSON must degrade to "no fields," never crash or half-parse.**
  **Verified**: `test_extract_json_malformed_returns_empty`,
  `test_extract_json_non_object_returns_empty`, and
  `test_extract_json_never_raises_on_pathological_input` (a few thousand
  unmatched braces) all pass.

## Verification

- [x] `uv run pytest` — `tests/test_extract.py` (`extract_json` cases),
      `tests/test_log_model.py` (`extract_fields()` combining regex + JSON,
      collision precedence, default-off, out-of-range row), and
      `tests/test_main_window_settings.py` (live detail-pane toggle, settings
      round-trip) — all green.
- [x] `uv run ruff check .` / `ruff format --check .` clean. (Caught and fixed
      a real bug in passing: `ruff format` mangled a parenthesized
      `except (ValueError, TypeError):` into invalid `except ValueError,
      TypeError:` syntax in `core/extract.py` — the same pre-existing
      formatter quirk `core/settings.py::load_settings` already works around
      by splitting into two `except` clauses. Applied the identical
      workaround here; verified with `ast.parse` and a full test re-run
      afterward.)
- [x] Manual (`run-zlog` `json-autodetect` scenario, screenshotted): a message
      with an embedded JSON object (including a nested `user.id`) shows all
      three fields correctly in the detail pane once the toggle is on.
- [ ] Perf smoke against a large capture — **not applicable**, since the
      `field:` filter gate this would have measured wasn't built.
- [ ] The ring-buffer eviction case — **not applicable** for the same reason;
      the shipped code path never caches per-row state, so there's nothing to
      re-key on eviction.

## Open questions

- **Is the perf/caching complexity worth it** versus leaving field access to
  the existing detail-pane flow? **Resolved for now: no** — this pass shipped
  the detail-pane-only version and left the filter gate unbuilt. Revisit if a
  concrete workload shows up where "open the detail pane to check a field" is
  genuinely insufficient and a real `field:` filter earns its complexity.
- **Global or per-format JSON auto-detect?** Resolved as leaned: a single
  global toggle (`json_autodetect_action`), matching the existing regex
  extractor list's scope.
