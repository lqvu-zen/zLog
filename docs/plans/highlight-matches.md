# Plan: Highlight matches (find mode)

- **Status:** Draft
- **Owner:** Vũ
- **Created:** 2026-07-08
- **Related:** regex-search, tag-highlight, theming

## Goal

Let the search term *highlight* matching rows while still showing everything (a
find-style overlay), as an alternative to the current filter-only behavior.

## Scope

- **In:** a **Filter / Highlight** mode toggle next to the search box. In Highlight
  mode the proxy shows all rows and matching rows get a tint (from the theme); in
  Filter mode behavior is unchanged. Mode persisted.
- **Out:** simultaneous filter+highlight with two different terms; match navigation
  (next/prev) — a possible follow-up.

## Design

The matcher already exists; highlight reuses it in the model's BackgroundRole.

| File | Layer | Change |
|---|---|---|
| `src/zlog/ui/theme.py` | ui | Add a `search_highlight` tint to each `Theme`. |
| `src/zlog/ui/log_model.py` | ui | Model gains an optional highlight matcher; `data()` BackgroundRole returns the highlight tint when a row matches (over level tint, under tag highlight). |
| `src/zlog/ui/main_window.py` | ui | Mode toggle: Filter → `proxy.set_search`; Highlight → clear the proxy search and push the matcher to the model instead. Persisted via settings (`search_mode`). |
| `src/zlog/core/settings.py` | core | Add `"search_mode": "filter"` to `DEFAULTS`. |

## Architecture touch points

- Precedence in BackgroundRole: tag highlight > search highlight > level tint
  (documented). Colors come from `ui/theme.py` (centralize-colors rule).
- Model stays virtualized; highlight is computed per visible row in `data()`.
- Versioning: no bump.

## Risks & regressions to check

- Switching modes clears the other's effect (no stale filter left applied).
- Invalid regex in Highlight mode keeps the previous highlight, mirrors filter behavior.
- Round-trip of `search_mode`; spec-parity assert holds.

## Verification

- [ ] `uv run pytest` (model highlight tests + settings round-trip)
- [ ] `uv run ruff check .` and `uv run ruff format --check .`
- [ ] Headless: highlight mode tints matches while row count stays full
