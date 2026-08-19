# Plan: Symbolicate/deobfuscate Android crash stack traces

- **Status:** Done
  <!-- Draft | Approved | In progress | Done | Abandoned -->
- **Owner:** unassigned
- **Created:** 2026-08-19
- **Related:** [crash-anr-detector.md](crash-anr-detector.md), [stack-trace-folding.md](stack-trace-folding.md), [bundle-adb.md](bundle-adb.md), [redaction-on-export.md](redaction-on-export.md), [custom-log-format-editor.md](custom-log-format-editor.md)

## Goal

A crash trace that today reads `at com.example.app.a.a(SourceFile:23)` (Java/Kotlin,
ProGuard/R8-minified) or `#00 pc 0001a2b4 libfoo.so` (native/NDK) reads with real
class/method names and, for native frames, real function names — everywhere the
message is shown or exported — once the user points zLog at the matching
**mapping.txt** and/or **native symbol files** for that exact build.

One plan covers both, deliberately (per explicit request) — they share the same
UI entry point and the same "apply at display time, never mutate the raw
capture" architecture, even though the two resolution mechanisms are
unrelated under the hood.

## Scope

- **In:**
  - Java/Kotlin: parse a ProGuard/R8 `mapping.txt`, deobfuscate class names,
    method names (line-range-aware where the mapping gives one), and the
    exception header itself.
  - Native: parse `#NN pc <offset> <lib>.so` backtrace frames, resolve the
    offset against a user-supplied directory of **unstripped** `.so` files via
    `addr2line`/`llvm-addr2line`, substitute the resolved function name.
  - A new **Symbol bar** under the device bar: load/clear a mapping file, load/clear
    a native symbols directory, an on/off toggle.
  - Applied to: the live log view (delegate paint), the detail pane, and
    copy/export/save.
  - Persisted across launches (paths remembered; re-applied automatically if
    the files still exist).
- **Out (non-goals):**
  - ProGuard's full inlining chains (`retrace -verbose`-style "inlined from A,
    inlined from B" multi-level output) — v1 resolves the direct mapping only;
    an inlined frame gets its best single guess, not a chain. Documented as a
    known gap, not silently wrong-but-confident.
  - Auto-downloading mapping/symbol files from Play Console or a build server.
  - Auto-detecting an NDK install to find `addr2line` — the user points at it
    once in Settings, like the adb path.
  - Making `level:`/`tag:`/search/regex filtering symbol-aware — filtering
    still matches the **raw** captured text; only what's *displayed* is
    deobfuscated. Searching for a real method name won't find it unless it
    also happens to appear raw. (See "Why filtering stays raw" below.)
  - iOS/other platforms — Android only, as asked.

## Why filtering stays raw (design decision)

Two ways this could have gone: (a) deobfuscate the *stored* message so every
consumer — filter, search, export — automatically sees real names, or (b)
keep the stored message untouched and apply the transform only where text is
*displayed*.

**(b) is the design**, for reasons that also happened to work out well for
architecture:

- **Native resolution requires a subprocess call** (`addr2line`) that cannot
  happen synchronously at parse time without stalling every reader thread on
  every batch. It has to be resolved asynchronously and cached — which means
  the raw message has to keep existing independently of whatever's been
  resolved so far.
- **Symbols can be loaded *after* lines are already captured** (you attach
  zLog, watch a crash happen live, *then* go find the mapping.txt for that
  build) — unlike the log-format editor, there's no "reload from file" escape
  hatch for a live stream. An overlay that's recomputed on demand handles a
  live stream and a loaded file identically; baking it into stored entries
  would only work for the reload-a-file case (mirrors why `redact_entries`
  already never mutates the master list — see `redaction-on-export.md`).
- **A wrong mapping produces a wrong name, not a "not found."** Keeping the
  raw text as the ground truth and reapplying the resolver on demand means
  swapping to the *correct* mapping/symbols instantly fixes every row — no
  stale baked-in wrong names to un-bake.

## Design — Phase 1: Java/Kotlin (ProGuard/R8 `mapping.txt`)

Pure text substitution against a well-documented mapping format. No
subprocess, no async, no cache needed — this half is genuinely simple.

| File | Layer | Change |
|---|---|---|
| `src/zlog/core/proguard.py` (new) | core | `ClassMapping(original, obfuscated)`; `MemberMapping(original_name, obfuscated_name, start_line, end_line)` (line range is in *original*-source terms, matching R8/ProGuard's `startline:endline:signature -> name` member-line format; a member line with no range applies to all lines). `parse_mapping(text: str) -> ProguardMapping` — a small line-based parser (class lines have no leading whitespace and end in `:`; member lines are indented, belong to the most recently seen class line). `ProguardMapping.deobfuscate_class(name: str) -> str` (unmapped names pass through unchanged — never guessed, same rule as `core/logformat.py`'s `apply_aliases`). `ProguardMapping.deobfuscate_member(obf_class: str, obf_member: str, line: int \| None) -> str` (line-range match when ambiguous and a line number is available; falls back to the first candidate — an accepted, documented limitation, not silently "correct"). `deobfuscate_line(mapping, message: str) -> str` — the line-level entry point: recognizes `at <class>.<member>(<file>:<line>)` (via `core.trace.is_stack_frame`'s existing pattern, extended to also capture class/member/line), an exception-header line (`<class>: <message>` / `Caused by: <class>`), and any other bare occurrence of a known obfuscated class name; rewrites what it recognizes, passes everything else through untouched. |
| `tests/test_proguard.py` (new) | tests | Parse a small real-shaped `mapping.txt` fixture (multiple classes, overloaded/line-ranged members); deobfuscate a full multi-frame trace built from it, asserting every class/method name and that the file name (`SourceFile`) becomes the real simple class name; an unmapped class/member passes through unchanged; a member with no line-number info available still resolves when there's exactly one candidate; ambiguous overloads without a line match resolve to *a* candidate, not a crash. |

## Design — Phase 2: Native (NDK) symbolication

Needs a subprocess toolchain (`addr2line`) and an unstripped `.so`, so this
half is architecturally closer to `bundle-adb.md`'s shape (external tool,
user-supplied path, resolved once and cached, never trusted blindly) than to
Phase 1.

**Frame format:** `#NN pc <hex offset> <path>/<lib>.so` (tombstone/backtrace
style, the format `adb logcat`/tombstones actually emit), optionally already
followed by `(symbol+offset)` if the binary isn't fully stripped — that case
needs no resolution at all.

**Resolving which `.so` to use, in order (never guess past this list — an
unresolved frame stays raw, which is safer than a wrong symbol):**

1. `<symbols_dir>/<lib>.so` (flat directory).
2. `<symbols_dir>/<abi>/<lib>.so`, where `<abi>` comes from a *currently
   attached* device (`adb shell getprop ro.product.cpu.abi`) — best-effort,
   skipped if no device is attached or the property read fails.
3. Exactly one match for `**/<lib>.so` under `symbols_dir` (recursive) — used
   only when it's unambiguous.
4. Otherwise: unresolved. The frame is left as-is; it is *not* guessed from
   multiple ABI candidates.

**Resolution is asynchronous and cached** — never blocks paint, never runs a
subprocess per row per repaint:

| File | Layer | Change |
|---|---|---|
| `src/zlog/core/native_trace.py` (new) | core | `NativeFrame(lib: str, offset: str)`; `parse_native_frame(message: str) -> NativeFrame \| None` (regex on the format above; also recognizes an already-symbolicated frame and returns `None` for it — nothing to resolve). `rewrite_native_frame(message: str, symbol: str) -> str` — inserts the resolved name in the same place `ndk-stack` does (` (symbol)` appended after the lib path), leaving the rest of the line untouched. |
| `src/zlog/core/addr2line.py` (new) | core | Pure command/output plumbing, no subprocess execution here (mirrors `core/parser.py` staying pure while `adb/reader.py` does the actual `Popen`): `build_command(exe: str, so_path: str) -> list[str]` (`[exe, "-f", "-C", "-e", so_path]`, batch mode — offsets go via stdin, one per line); `parse_output(raw: str, offsets: list[str]) -> dict[str, str]` (addr2line with `-f` prints two lines per input address — function name, then file:line; pairs them back up positionally with the input offsets, in order). |
| `src/zlog/core/native_symbols.py` (new) | core | `find_symbol_file(symbols_dir: str, lib: str, device_abi: str \| None, listdir, glob) -> str \| None` implementing the 4-step order above, with filesystem calls injected (same testability pattern as `core/adbpath.py`'s `path_lookup`/`managed` callables) — pure logic, unit-testable with a fake filesystem. |
| `src/zlog/ui/native_symbolicator.py` (new) | ui | `NativeSymbolResolver(QThread)` — takes a batch of `(lib, offset)` pairs, the symbols dir, the addr2line exe path, and (optionally) the attached device's ABI; groups offsets by resolved `.so` path (via `find_symbol_file`), shells out once per distinct library (not once per frame), emits `resolved(dict[(lib, offset), str \| None])` on completion. Same signal-only, cancellable contract as `AdbFetcher`/every other reader. A missing `addr2line`, a `.so` that can't be found, or a subprocess error resolves that batch to `None` per offset (shown raw) rather than raising into the UI thread. |
| `src/zlog/ui/main_window.py` | ui | Owns a `NativeSymbolCache: dict[tuple[str, str], str \| None]` (`(lib, offset) -> symbol`, `None` = tried and failed, absent = not yet attempted). On each `append_entries` batch (when a native symbols dir is configured and the toggle is on), scan the new entries with `parse_native_frame`, collect offsets not already in the cache, hand them to a `NativeSymbolResolver` job. On `resolved`, merge into the cache and repaint (`table.viewport().update()`) plus refresh the detail pane if the current selection was affected. |
| `tests/test_native_trace.py`, `test_addr2line.py`, `test_native_symbols.py` (new) | tests | Frame parsing (recognizes the format, ignores an already-symbolicated frame); `find_symbol_file`'s 4-step order against a fake directory listing (flat hit, ABI-subfolder hit via a stubbed `getprop`, unambiguous recursive hit, and the "give up" case with 0 or 2+ candidates); `build_command`/`parse_output` against real-shaped `addr2line -f -C` output. |
| `tests/test_native_symbolicator.py` (new) | tests | `NativeSymbolResolver` against a stubbed `subprocess.run` — batches offsets per library correctly, missing exe / missing `.so` / a subprocess error all resolve to `None` rather than raising, cancellation mid-batch leaves the cache untouched for that batch. |

## Design — the shared "Symbol bar" and wiring

| File | Layer | Change |
|---|---|---|
| `src/zlog/core/symbolicate.py` (new) | core | `Symbolicator` — holds an optional `ProguardMapping` and an optional `native_cache: Mapping[tuple[str,str], str \| None]` (injected, read-only from this object's point of view — it does no I/O and no threading). `apply(message: str) -> str`: try `parse_native_frame` first (rewrite via the cache if resolved, else unchanged), else try Java deobfuscation if a mapping is loaded, else return unchanged. This is the single call site every display/export path goes through. |
| `src/zlog/ui/build.py` | ui | New `symbol_row` (`QHBoxLayout`), inserted **between** `top_row` (device bar) and `filter_row` (query bar) in `build_layout`'s outer `QVBoxLayout` — literally under the device bar, per the request. Contents: `QLabel("Mapping:")` · `win.mapping_path_edit` (read-only `QLineEdit`, tooltip = full path) · `win.load_mapping_btn` ("Load…") · `win.clear_mapping_btn` ("Clear") · `_vsep()` · `QLabel("Native symbols:")` · `win.symbols_dir_edit` (read-only, tooltip = full path) · `win.load_symbols_btn` ("Load…") · `win.clear_symbols_btn` ("Clear") · `addStretch(1)` · `win.symbolicate_check` (`QCheckBox("Symbolicate")`, default checked). |
| `src/zlog/ui/main_window.py` | ui | `self._symbolicator = Symbolicator()`. `_load_mapping_file()`: `QFileDialog.getOpenFileName`, `parse_mapping` (catch/report a parse error via the status bar, same shape as an invalid regex elsewhere — never crash on a bad file), store, update `self._symbolicator`, refresh the view. `_load_native_symbols_dir()`: `QFileDialog.getExistingDirectory`, store the path (existence is checked lazily per-frame by `find_symbol_file`, not eagerly). Matching `_clear_*` handlers. `symbolicate_check` toggled → swap `self._symbolicator` for a no-op one and back (cheap: the loaded mapping/cache aren't discarded, just not applied) and repaint. Delegate gets `win.log_delegate.symbolicator = self._symbolicator` (a plain attribute, same shape as `.wrap`/`.line_numbers`); `_update_detail` calls `self._symbolicator.apply(entry.message)` instead of the raw field. |
| `src/zlog/ui/log_delegate.py` | ui | `LogItemDelegate.__init__` gains `self.symbolicator = None`. Both `entry.message` read sites: `message = self.symbolicator.apply(entry.message) if self.symbolicator else entry.message`. Paint-time cost is a dict lookup (native, already resolved) or a small regex+dict pass (Java) — cheap, and only visible rows are ever painted, so this stays consistent with the model's virtualization guarantee. |
| `src/zlog/ui/export_actions.py` | ui | `symbolicate_entries(entries: list[LogEntry], symbolicator: Symbolicator \| None) -> list[LogEntry]` — mirrors `maybe_redact`/`redact_entries` exactly (`dataclasses.replace` per entry, only when the message actually changes). Applied unconditionally (no separate opt-in checkbox, unlike redaction — see below) in `_write_log`/`_export`/copy, composed with `maybe_redact` (symbolicate first, then redact, so a de-obfuscated real class name can still be redaction-masked if it happens to look like a token). |
| `src/zlog/core/settings.py` | core | New `DEFAULTS` keys: `"mapping_path": ""`, `"symbols_dir": ""`, `"addr2line_path": ""`, `"symbolicate_enabled": True`. |
| `src/zlog/ui/settings_dialog.py` | ui | Capture tab gains an `addr2line path` row (text field + Browse…), same shape as the existing `adb path` row — a one-time environment/toolchain setting, deliberately **not** in the main Symbol bar (which is for the two per-investigation inputs: which mapping, which symbols). |
| `src/zlog/ui/main_window.py` | ui | `_settings_specs()` gains entries for the four new keys (mirroring `adb_path`'s registration); on startup, if a saved `mapping_path`/`symbols_dir` still exists on disk, silently reload it (mirrors `formats_from_json`'s defensive-skip elsewhere — a moved/deleted file is dropped quietly, not an error dialog on every launch). |
| `tests/test_symbolicate.py` (new) | tests | `Symbolicator.apply` composes native-then-Java correctly, no-op with nothing loaded, doesn't crash on a message that matches neither shape. |
| `tests/test_main_window_symbolicate.py` (new) | tests | Loading a mapping file updates the delegate/detail pane output for a known obfuscated line; the toggle actually toggles (checked → deobfuscated, unchecked → raw) without discarding the loaded mapping; export/copy reflect the same deobfuscated text as the view; settings round-trip (paths persisted and reloaded on a fresh `MainWindow`, a since-deleted path is dropped without error). |

## Global, not per-tab (design decision)

Unlike the log-format editor (deliberately per-tab, since different tabs can
legitimately be different apps/formats), the mapping file, symbols directory,
and toggle are **global settings**, same as `adb_path`. Rationale: symbol
files are tied to "the build I'm currently debugging," which is far more
often one investigation across several device tabs than several unrelated
apps at once — and a global setting is simpler to reason about and persist.
If real use shows people juggling multiple apps' symbols simultaneously,
that's a concrete case to revisit this against, not a hypothetical to design
around now.

## Architecture touch points

- **Threading:** native resolution runs on a `QThread` (`NativeSymbolResolver`),
  signal-only back to the UI (`resolved(dict)`), same contract as every other
  reader/fetcher. Java deobfuscation is synchronous (pure, in-memory, no I/O
  once `mapping.txt` is parsed) — safe to call at paint time directly.
- **Model/proxy:** none — this doesn't add a column or a filter predicate; it
  changes what text is *shown* for the existing message field.
- **Dependency direction:** `core/proguard.py`, `core/native_trace.py`,
  `core/addr2line.py`, `core/native_symbols.py`, `core/symbolicate.py` are all
  Qt-free and I/O-free (filesystem/subprocess calls injected or pushed to
  `ui/`), matching `core/adbpath.py`'s existing shape. `ui/native_symbolicator.py`
  is the one place an actual subprocess runs, exactly analogous to
  `adb/reader.py` being the one place `adb logcat` actually runs.

## Risks & regressions to check

- **A wrong mapping/symbols file must not look confidently right.** Every
  resolution rule above explicitly refuses to guess past its documented
  fallback order — an unresolved frame stays in its raw, honest form. This is
  the single most important property of the whole feature; test it as
  deliberately as the successful-resolution cases.
- **Native resolution must never block the UI thread.** No subprocess call
  anywhere in the delegate's paint path — verify by grep, not just by design
  intent (a `subprocess.run` that sneaks into `Symbolicator.apply` would be a
  silent regression, not a crash, so it's easy to miss without deliberately
  checking).
- **A missing/invalid `addr2line`** must degrade to "frames stay raw," not a
  crash or a startup nag — same posture zLog already takes toward a missing
  `adb` (`usable-without-adb.md`).
- **Cache correctness across a Clear/reload:** clearing the mapping or
  symbols dir must actually stop applying the old one (not just stop loading
  new resolutions) — verify the toggle/clear paths actually swap out the
  `Symbolicator`/cache, not just null a path string that nothing re-checks.
- **Ring-buffer cap interaction:** the native symbol cache is keyed by
  `(lib, offset)`, not by row index, so evicting old rows from the model
  (`max_rows`) doesn't need any remap — unlike bookmarks/incidents. Worth a
  test confirming this explicitly rather than assuming it from the design.
- **Large mapping.txt files:** a big app's mapping.txt can be tens of
  thousands of lines — `parse_mapping` should be a single linear pass, not
  something quadratic; time it against a real large mapping file before
  calling this done.
- **`SourceFile` rewriting must not clobber a message that legitimately
  contains the literal text "SourceFile"** for unrelated reasons — only rewrite
  it inside a recognized `at Class.method(SourceFile:N)` frame, never as a
  bare find-and-replace across the whole message.

## Verification

- [x] Every phase's unit tests pass, built from real-shaped fixtures (a real
      ProGuard/R8 `mapping.txt` shape with overloaded/line-ranged members and
      nested classes; real `addr2line -f -C` output shape). `test_proguard.py`
      (12), `test_native_trace.py` (7), `test_addr2line.py` (6),
      `test_native_symbols.py` (8), `test_symbolicate.py` (7),
      `test_native_symbolicator.py` (6), `test_adb_devices.py`'s new
      `device_abi` tests (4) — 50 new core/adb-layer tests, all green.
- [x] A multi-frame Java/Kotlin crash trace, run through a real `mapping.txt`
      shape, reads correctly end to end — class name, method name, the
      exception header, and the `(SourceFile:N)`→`(MainActivity:N)` rewrite —
      verified both in unit tests and visually via the `run-zlog`
      `crash-symbolication` scenario.
- [x] A native backtrace resolves end to end through the async/cache path —
      `test_native_frame_resolution_pipeline_updates_the_cache_and_view`
      drives the real `_maybe_resolve_native_frames` → resolver →
      `_on_native_resolved` → cache → repaint chain (with a fake resolver
      standing in for the real subprocess, verified separately in
      `test_native_symbolicator.py`) and confirms the detail pane updates
      only after resolution lands, not before.
- [x] Unresolved cases all leave the original text visible rather than
      guessing or crashing: unmapped Java class/member (`test_proguard.py`),
      missing `.so` / ambiguous ABI (`test_native_symbols.py`'s give-up
      cases), missing/failing `addr2line` (`test_native_symbolicator.py`'s
      OSError/timeout cases) — none of these raise into the UI.
- [x] The Symbolicate toggle actually toggles without losing the loaded
      mapping/symbols —
      `test_toggle_off_shows_raw_without_discarding_the_mapping`.
- [x] Export/copy match what the live view shows —
      `test_selected_text_reflects_the_symbolicated_message`,
      `test_save_log_writes_symbolicated_text`; `export_actions.py`'s
      `write_log`/`export_formatted`/`export_pdf` and all four copy handlers
      route through the same `symbolicate_entries`.
- [x] Settings round-trip: `test_settings_round_trip_reloads_and_reparses_the_mapping`,
      `test_native_symbols_dir_round_trips`; a since-deleted mapping path
      degrades quietly — `test_deleted_mapping_path_is_dropped_quietly_on_reload`.
- [x] Screenshot via `run-zlog` (`crash-symbolication` scenario): the Symbol
      bar sits directly under the device bar, above the query row; a Java
      trace shows fully deobfuscated (`NetworkException`,
      `MainActivity.onCreate(MainActivity:1)`) and a native frame shows its
      resolved symbol (`crash_handler+32`) next to the raw offset.
- [x] `uv run ruff check .` / `ruff format --check .` — clean, repo-wide.
      Caught and fixed a real bug along the way: the installed ruff's
      formatter mangles a parenthesized `except (A, B)` tuple into invalid
      `except A, B:` syntax (a known, already-documented issue in
      `core/settings.py`) — hit it fresh in `adb/devices.py` and
      `ui/native_symbolicator.py`; fixed both by splitting into separate
      `except` clauses, the same workaround already in use elsewhere.
- [x] Targeted tests green across every touched file (proguard/native/addr2line/
      symbolicate/native_symbolicator/adb_devices, plus regression coverage on
      `log_delegate`, `main_window_settings`, `settings_dialog`, `export`,
      `pdf_export`, `redact`, `settings`, `main_window_tabs` — 213 tests,
      1 pre-existing test needed updating for the new `addr2line_path` key in
      `SettingsDialog.get_values()`, fixed). Full-suite verification is a
      separate `qa-zlog` pass, not part of landing this.

## Open questions (resolved)

- **Ambiguous-overload fallback (Java):** resolved as "first candidate" —
  shipped as designed. A plausible name beats an obfuscated one even when
  overload disambiguation isn't possible; documented as a known limitation
  in `proguard.py`'s docstring and covered by
  `test_disambiguates_overloaded_method_by_line_range`.
- **Multiple simultaneous mapping/symbol sets:** stays out of scope per the
  global design decision — revisit only if real use shows it's needed.
