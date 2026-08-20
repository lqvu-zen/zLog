# Plan: JSON auto-fields + a `field:` query token

- **Status:** Approved  <!-- Draft | Approved | In progress | Done | Abandoned -->
- **Owner:** unassigned
- **Created:** 2026-08-20
- **Related:** [regex-extract-columns.md](regex-extract-columns.md), [tag-summary.md](tag-summary.md)

## Goal

A line whose message is (or contains) a JSON object gets its keys parsed into
named fields with **no user regex**, and any extracted field — from JSON or from
the existing user regex extractors — becomes filterable via a new
`field.<name>:<value>` query token. This is the filter capability
[regex-extract-columns.md](regex-extract-columns.md) deliberately shipped
without ("no filter change in phase 1" — left as its open question).

## Scope

- **In:** a JSON auto-extractor in `core/extract.py`; a toggle to enable it
  alongside the existing regex-extractor list; a `field.<name>:<value>` query
  token (substring match against that field's extracted value, same style as
  every other query token); the proxy gate that makes it filter.
- **Out (non-goals):** typed comparisons (`>`, `<`, ranges) — string-substring
  only, matching the rest of the query language; nested JSON beyond one flatten
  level; turning extracted fields into sortable inline columns (still no column
  model, per the parent plan's decision — unchanged here).

## Design

| File | Layer | Change |
|---|---|---|
| `src/zlog/core/extract.py` | core | `extract_json(message: str) -> dict[str, str]`: try `json.loads` on the whole message, else the first balanced `{...}` substring; flatten one level; stringify values; return `{}` on any failure (never raises — mirrors `compile_extractors` swallowing bad regexes). |
| `src/zlog/core/query.py` | core | `QuerySpec` gains `fields: tuple[tuple[str, str], ...]` (name, value-substring pairs); `field.<name>:<value>` tokens parsed like `tag:`/`proc:`; `_classify`/`token_spans` gain a `"field"` kind for query-bar highlighting. |
| `src/zlog/ui/log_model.py` | ui | `LogFilterProxy` gains a `set_json_autodetect(bool)` and reads `spec.fields`; `filterAcceptsRow` calls into the model's existing `extract_fields(source_row)` (already used by `EXTRACT_ROLE`, `log_model.py:477`) to test each requested field. See Risks — this needs a cache, not a live extract on every filter pass. |
| `src/zlog/ui/main_window.py` | ui | "Auto-detect JSON fields" toggle (View menu, alongside `extract_act`); persists `json_autodetect` in settings; wires `proxy.set_json_autodetect`. |
| `src/zlog/core/settings.py` | core | `"json_autodetect": False` in `DEFAULTS`. |
| `tests/test_extract.py` | — | `extract_json`: object message, message with a trailing JSON blob, malformed JSON → `{}`, nested object flattened one level. |
| `tests/test_query.py` | — | `field.name:value` parses into `QuerySpec.fields`; `token_spans` classifies it. |
| `tests/test_log_model.py` | — | Filtering by `field.*` gate, combined with an existing regex extractor. |

## Architecture touch points

- **Model/proxy:** a new filter predicate. This is the one place the design
  needs care (see Risks) — every other proxy gate reads a plain `LogEntry`
  attribute; this one requires running an extractor over the message first.
- **Dependency direction:** `core/extract.py` and `core/query.py` stay Qt-free;
  the proxy wiring is `ui`-only.
- **Threading:** none.

## Risks & regressions to check

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
  is itself the cost the cache above exists to bound.
- **Invalid/absent JSON must degrade to "no fields," never crash or half-parse.**

## Verification

- [ ] `uv run pytest` (new extract/query/model cases above)
- [ ] `uv run ruff check .` / `ruff format --check .`
- [ ] Perf smoke: apply a `field.*:` filter against a large synthetic capture
      (≥100k rows) with JSON auto-detect on; compare timing against the same
      filter without the cache to confirm the mitigation actually avoids
      re-extracting on every pass.
- [ ] Manual: `run-zlog` scenario opening a JSON-lines sample file, applying
      `field.level:error`-shaped query, screenshot the filtered view.
- [ ] The ring-buffer eviction case above, exercised with a small `max_rows` cap
      in a test.

## Open questions

- **Is the perf/caching complexity worth it** versus leaving field access to
  the existing detail-pane + summary-dialog-generates-a-query flow
  (`regex-extract-columns.md`'s option (a), already shipped)? This plan should
  not proceed past Draft without confirming there's a real workload where the
  summary-dialog flow is insufficient.
- **Global or per-format JSON auto-detect?** Leaning global toggle (like the
  existing regex extractor list), simplest to reason about.
