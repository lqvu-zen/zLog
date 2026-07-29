# Plan: Narrower Saved Filters sidebar

- **Status:** Done  <!-- Draft | Approved | In progress | Done | Abandoned -->
- **Owner:** unassigned
- **Created:** 2026-07-29
- **Related:** [saved-filters-sidebar.md](saved-filters-sidebar.md)

## Goal

Give the **Saved Filters** left dock a smaller initial width, so it takes less
of the window by default (still freely resizable by dragging).

## Scope

- **In:** set an explicit, smaller initial width for `presets_dock` at
  construction time.
- **Out (non-goals):** capping how wide the user can drag it, persisting a
  user-resized width across launches (not done today either), changing the
  Bookmarks dock (right side, hidden by default, unaffected).

## Design

| File | Layer | Change |
|---|---|---|
| `src/zlog/ui/main_window.py` | ui | New `showEvent` override calls `self.resizeDocks([self.presets_dock], [160], Qt.Horizontal)` once, via a zero-delay `QTimer.singleShot`, guarded by a new `self._docks_sized` flag so a later show (e.g. un-minimizing) doesn't re-narrow a dock the user has since widened. |

**Why not `build.py`, at construction time (like `_splitter.setSizes(...)`)?** Tried
that first — `resizeDocks` silently no-ops before the window has real geometry, and
even calling it synchronously from `showEvent` gets overwritten by the dock
layout's own first pass. It only sticks once deferred to right after that pass
settles (a `QTimer.singleShot(0, ...)` scheduled from `showEvent`). Confirmed with
a throwaway script against the real "windows" Qt platform: default width 268px →
160px with this fix.
| `tests/test_main_window_settings.py` | tests | `test_show_narrows_the_presets_dock_once` — spies on `resizeDocks` (monkeypatched instance attribute) rather than asserting a pixel width, since the offscreen Qt platform used by the whole suite doesn't reproduce real dock-layout geometry (see Risks). Asserts one call on first `show()` and no second call on a later one. |

## Architecture touch points

None — pure layout, no threading/model changes.

## Risks & regressions to check

- The dock must still be freely resizable (drag the splitter handle) and still
  show the preset list/preview usably at the smaller default.
- Doesn't affect the Bookmarks dock or the log/detail splitter.
- **The offscreen Qt platform (`QT_QPA_PLATFORM=offscreen`, used by both
  `run-zlog`'s headless screenshots and the whole pytest suite per
  `tests/conftest.py`) does not reproduce `QMainWindowLayout`'s real dock-sizing
  behavior** — `resizeDocks` calls are accepted but the dock stays pinned at a
  fixed ~86px regardless of the requested size, both before and after this fix,
  confirmed by direct experimentation. A screenshot diff or a pixel-width
  assertion would show *no change* under either the driver or pytest even though
  the fix works. Verified instead with a throwaway script run against the real
  `windows` Qt platform (see Design) and a wiring test that spies on the
  `resizeDocks` call rather than measuring pixels.

## Verification

- [x] `uv run pytest` (`test_show_narrows_the_presets_dock_once`, wiring-only —
      see the offscreen-platform caveat above)
- [x] `uv run ruff check .` and `uv run ruff format --check .`
- [x] Manual: throwaway script against the real `windows` Qt platform confirmed
      268px (default) → 160px (with this fix) — see Design
- [ ] `run-zlog` screenshot — **not usable for this change**; the offscreen
      platform doesn't show the difference (see Risks). Left unchecked rather
      than falsely marked verified.

## Open questions

None — width picked as a reasonable default (268px → 160px); the user can
always drag it wider.
