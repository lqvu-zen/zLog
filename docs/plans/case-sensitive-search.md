# Plan: Case-sensitive search toggle

- **Status:** Done
- **Owner:** Vũ
- **Created:** 2026-07-07
- **Related:** regex-search.md, refactor-main-window.md (uses the new settings spec)

## Goal

Add a **Case** checkbox next to Regex so the search box can match case-sensitively
(both substring and regex modes); default stays case-insensitive as today.

## Scope

- **In:** a `case` flag threaded core → proxy → UI; a persisted **Case** checkbox;
  Clear Filters also resets it.
- **Out:** per-column case rules, whole-word matching, changing the default (stays
  insensitive).

## Design

| File | Layer | Change |
|---|---|---|
| `src/zlog/core/search.py` | core | `compile_matcher(text, regex, case=False)`. `case=True` drops `re.IGNORECASE` (regex) and compares without lowercasing (substring). Default preserves current behavior. |
| `tests/test_search.py` | core | Add case-sensitive substring + regex cases (insensitive default still holds). |
| `src/zlog/ui/log_model.py` | ui | `set_search(text, regex, case=False)` forwards `case` to `compile_matcher`. |
| `src/zlog/core/settings.py` | core | Add `"case": False` to `DEFAULTS`. |
| `src/zlog/ui/main_window.py` | ui | Add `self.case_check` in `_build_widgets`, place it in row 2, connect `toggled → _apply_search`; `_apply_search` passes `self.case_check.isChecked()`; add a `case` settings spec row; `clear_filters()` unchecks it. |

## Architecture touch points

- **Threading / model:** none new. Same proxy filter path; `invalidateFilter` on change.
- **Dependency direction:** `core.search` stays Qt-free; `case` defaults keep the
  signature backward-compatible. UI → core only.
- **Settings:** new key is added to `DEFAULTS` *and* `_settings_specs()`; the parity
  assert added in the refactor guards that both are updated.
- **Versioning:** no bump.

## Risks & regressions to check

- Default (Case off) behavior byte-identical to today (insensitive substring + regex).
- Invalid regex still returns False and keeps the previous matcher, regardless of Case.
- Toggling Case re-runs the filter live; empty box still matches everything.
- Case state round-trips through save/restore; Clear Filters resets it.

## Verification

- [ ] `uv run pytest` (new case tests)
- [ ] `uv run ruff check .` and `uv run ruff format --check .`
- [ ] Headless: seed rows, toggle Case, assert visible set changes as expected;
      settings round-trip includes `case`
- [ ] `run-zlog` smoke: the Case box renders next to Regex
