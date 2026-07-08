# Plan: Doc sync + deprecation cleanup

- **Status:** Done
- **Owner:** Vũ
- **Created:** 2026-07-07
- **Related:** tech-debt-refactor.md (done), refactor-main-window.md (done)

## Goal

Bring the docs back in line with the code after the recent refactors, and silence the
`QSortFilterProxyModel.invalidateFilter()` deprecation warnings — two low-risk hygiene
fixes with no behavior change.

## Scope

- **In:**
  - Update `CLAUDE.md` "Where things live" and `docs/ARCHITECTURE.md` to mention
    `ui/device_controller.py` (device picker + package/PID filter state), the `case`
    search flag, and the offscreen-Qt test setup (`tests/conftest.py`, CI job).
  - Replace the 3 deprecated `self.invalidateFilter()` calls in
    `src/zlog/ui/log_model.py` with `self.invalidate()`.
- **Out:** any behavior change, new features, further refactors.

## Design

`invalidate()` re-runs the filter (and sorting) and is not deprecated on PySide6
6.11.1, whereas both `invalidateFilter()` and `invalidateRowsFilter()` are. The proxy
has no active sort, so `invalidate()` is functionally identical here — it just also
clears a sort that doesn't exist.

| File | Layer | Change |
|---|---|---|
| `src/zlog/ui/log_model.py` | ui | `self.invalidateFilter()` → `self.invalidate()` in `set_min_level`, `set_search`, `set_pids`. |
| `CLAUDE.md` | docs | Add `device_controller.py` to the "Where things live" table; note the `case` flag and offscreen test setup. |
| `docs/ARCHITECTURE.md` | docs | Note `DeviceController` in the `ui/` section. |

## Architecture touch points

- No threading/model/proxy semantics change; filter still re-evaluates on every setter.
- Dependency direction unchanged.
- Versioning: no bump.

## Risks & regressions to check

- Filtering still updates live when level/search/case/PID change (covered by
  `tests/test_log_model.py`).
- Deprecation warnings gone from the test run.

## Verification

- [ ] `uv run pytest` (warning count drops; all pass)
- [ ] `uv run ruff check .` and `uv run ruff format --check .`
- [ ] `grep -c invalidateFilter src/zlog/ui/log_model.py` == 0
- [ ] Docs mention `device_controller.py`
