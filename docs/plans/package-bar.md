# Plan: Restore the package/process selector bar

- **Status:** Done
- **Owner:** Vũ
- **Created:** 2026-07-09
- **Related:** two-bar-header.md, package-filter.md, logcat-style-ui.md

## Goal

Bring back a visible **package (process) selector** — dropdown + Load / Apply /
Clear pkg — as its own bar between the device bar and the filter box, complementing
the query bar's `package:` syntax.

## Scope

- **In:** place the existing (already-wired) `package_box`, `load_pkgs_btn`,
  `apply_pkg_btn`, `clear_pkg_btn` into a package row in `_build_layout`.
- **Out:** any behavior change — the widgets and their handlers already exist; this
  is layout only.

## Design

| File | Change |
|---|---|
| `src/zlog/ui/main_window.py` | `_build_layout` adds a `package_row` (`Package:` + combo + Load/Apply/Clear) between the device row and the filter row. |

## Verification

- [ ] `uv run pytest` / ruff (behavior unchanged)
- [ ] Headless screenshot shows Device bar / Package bar / Filter bar stacked
