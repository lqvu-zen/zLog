# Plan: App icon (Terminal Caret)

- **Status:** Done
  <!-- Draft | Approved | In progress | Done | Abandoned -->
- **Owner:** unassigned
- **Created:** 2026-08-17
- **Related:** [release-workflow.md](release-workflow.md)

## Goal

zLog's window, taskbar, and built `.exe` all show Qt's generic default icon
today. After this, they show a real zLog icon — the "Terminal Caret" concept
(chevron + cursor bar on a dark tile), the direction picked from three
proposed concepts built off the app's own theme colors.

## Scope

- **In:** icon source + rasterized assets, wiring into the running app's
  window/taskbar icon, wiring into the cx_Freeze `.exe` file icon.
- **Out (non-goals):** per-theme icon variants (the tile is dark and reads
  fine on both a light and dark taskbar, already checked in the concept
  review), a macOS `.icns` (project ships a Windows `.exe`; the PNG still
  gives a reasonable icon if ever run unfrozen elsewhere), redesigning the
  concept itself (already picked).

## Design

The chosen SVG (256×256 viewBox): a rounded-square tile (`rx=56`, ~22%
corner radius, matching Windows 11's icon convention), fill `#101418`; a
chevron `>` drawn as a 26px-wide rounded-cap/join stroke in `#59c6ff` from
(74,82) to (138,128) to (74,174); a cursor bar — rounded rect at (150,160),
60×24, `rx=8`, same `#59c6ff` fill.

| File | Layer | Change |
|---|---|---|
| `src/zlog/assets/icon.svg` | asset | The source vector (hand-authored, matches the concept exactly) — kept for future edits/regeneration, not loaded at runtime. |
| `src/zlog/assets/icon.png` | asset | 256×256 raster of the same artwork, generated from the SVG geometry via Pillow (`ImageDraw`, no new dependency — Pillow is already used for `run-zlog` screenshots). Loaded by `QIcon` at runtime; Qt's PNG support is universal, so this is what actually renders the window/taskbar icon. |
| `src/zlog/assets/icon.ico` | asset | Multi-resolution ICO (16/24/32/48/64/128/256) built with Pillow's ICO writer from the same source raster, downsampled per size. Used only by cx_Freeze for the compiled `.exe`'s Windows file icon — `.ico` is the format Windows PE icons require, a `.png` won't work there. |
| `src/zlog/app.py` | ui-bootstrap | After `QApplication(...)` is constructed: `app.setWindowIcon(QIcon(_icon_path()))`, where `_icon_path()` resolves `Path(__file__).resolve().parent / "assets" / "icon.png"`. `QApplication.setWindowIcon` is inherited by every top-level window that doesn't set its own (confirmed: `MainWindow` doesn't), so this one call covers the main window, its dialogs, and the taskbar/Alt-Tab icon — no `main_window.py` change needed. |
| `cxfreeze_setup.py` | build | `Executable(..., icon="src/zlog/assets/icon.ico")` sets the compiled `.exe`'s file icon (what Explorer/taskbar show for the file itself, before or after launch). `build_exe_options["include_files"] = [("src/zlog/assets", "lib/zlog/assets")]` guarantees the PNG is actually present at the path `_icon_path()` resolves to once frozen (verified: cx_Freeze mirrors `src/zlog/<x>` to `lib/zlog/<x>` for `.pyc`s; a package's own non-`.py` data files aren't picked up by the module finder automatically, so this needs to be explicit rather than assumed). |
| `tests/test_app_icon.py` (new) | — | Asset-integrity tests: `icon.png`/`icon.ico` exist, are non-empty, and are readable/valid image files (Pillow `Image.open` + `.verify()`); `app._icon_path()` resolves to an existing file. Cheap regression coverage against "someone deletes the asset and nobody notices until the taskbar looks wrong." |

## Architecture touch points

- **Threading / model / dependency direction:** none — this is bootstrap-time
  setup and a build-config change, no reader/model code touched.

## Risks & regressions to check

- **Frozen-build path resolution is the one real risk.** `_icon_path()` must
  resolve correctly both from source (`uv run zlog`) and inside the
  cx_Freeze build (`zlog.exe`) — verify against the actual built `.exe`, not
  just the source run, since that's exactly the kind of thing that "works on
  my machine" and breaks in the artifact.
- **The ICO must actually contain multiple resolutions** — a single-size ICO
  scaled by Windows looks soft in the taskbar; generate all of 16/24/32/48/64/128/256
  explicitly rather than relying on Windows to downscale one large image.
- **Don't let this bump `__version__`** — an icon isn't a release by itself
  (see `CLAUDE.md`'s "Version bumps happen only on release").

## Verification

- [x] `icon.png`/`icon.ico` open and match the intended artwork (visual
      check — read back and eyeballed against the Concept C mockup).
- [x] The cx_Freeze build produces a `zlog.exe` whose file icon (checked via
      `System.Drawing.Icon.ExtractAssociatedIcon` on the built `.exe`) is the
      new icon, and `lib/zlog/assets/` is present in the frozen tree.
- [x] Launched the built `zlog.exe`: a real top-level window came up
      (`MainWindowTitle=zLog - Live Log Viewer`), confirming
      `app.setWindowIcon(...)` ran without error on the actual frozen path,
      not just from source; stopped cleanly after.
- [x] `QIcon(_icon_path())` — the exact call `app.main()` makes — loads
      successfully and paints non-transparent pixels, verified directly in
      `test_qicon_actually_loads_the_png` (`qapp` fixture, offscreen Qt), not
      just inferred from the PNG header being well-formed.
- [x] `uv run pytest` — `test_app_icon.py` (new, 5 tests) plus
      `test_app_focus.py`/`test_applog.py` (existing `app.py`-adjacent
      coverage), 15/15 green. Not a full-suite run (see `no-full-suite-per-feature`
      practice — this change touches only `app.py`, `cxfreeze_setup.py`, and
      new assets, nothing shared).
- [x] `uv run ruff check .` / `ruff format --check .` — clean, repo-wide.

## Open questions

None — concept and wiring points are both settled.
