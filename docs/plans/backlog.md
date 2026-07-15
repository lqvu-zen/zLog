# Feature backlog — candidate features (to implement later)

- **Status:** Ideas (each item becomes its own Approved plan when we pick it up)
- **Owner:** unassigned
- **Created:** 2026-07-14

A survey of features that fit zLog. Grouped by theme; each entry lists **why**, a
**design sketch** (approach/files), **effort** (S/M/L), and whether the core logic is
**Qt-free-testable**. Priority buckets mirror the roadmap (P0 correctness/perf ·
P1 daily-driver UX · P2 power/delight · P3 bigger bets). "★" marks quick wins.

## Reading & navigation

- **★ Inline search-match highlight** (P1, S, core-testable) — highlight the matched
  *substring* inside each line, not just the row tint. Sketch: `core/spans.py`
  `find_spans(text, matcher) -> [(start,end)]`; delegate paints highlighted runs in the
  message; reuse the active search/highlight matcher.
- **Persistent highlight rules** (P1, M, core-testable) — user list of term/regex → color,
  always highlighted regardless of the current search (e.g. FATAL red, your package green).
  Sketch: `core/highlight_rules.py` (list of {pattern, regex, color}); Settings tab to
  manage; delegate/model apply on paint; persisted.
- **Stack-trace folding** (P2, L, core-testable) — collapse a Java exception's `at …`
  stack under its header line, expandable ("▶ … 27 more"). Sketch: `core/trace.py`
  groups consecutive stack lines; a fold state per group in the model; delegate shows a
  disclosure triangle; proxy hides folded lines.
- **★ Go to timestamp / line** (P1, S, core-testable) — "Go to time…" jumps to the first
  line at/after a typed time; "Go to line N". Sketch: `core/timefmt` parse + bisect over
  rows; select+scroll. Ctrl+G.
- **Jump to same tag / same PID** (P2, S) — from a line, next/prev occurrence of its tag
  or pid. Sketch: reuse match-navigation over a predicate.
- **Gutter line numbers** (P2, S) — optional source-row numbers in a left gutter (toggle).
- **Sticky header line** (P3, M) — pin the selected/bookmarked line to the top while
  scrolling.

## Filtering & search

- **★ Exclude by pid / proc** (P1, S, core-testable) — `-pid:1234` / `-proc:com.x` negatives
  to complement the existing include tokens; right-click "Exclude PID/Package".
  Sketch: extend `core/query.py` + proxy gates (mirror the include path).
- **Time-range filter** (P1, M, core-testable) — `since:HH:MM:SS` / `until:…` (or a
  range picker) to bound the view. Sketch: query tokens + a proxy time gate using
  `parse_logcat_time`.
- **Filter chips** (P2, M) — render active query tokens as removable chips above the bar
  for quick editing. Sketch: parse spec → chip row; click-to-remove rewrites the query.
- **Duplicate count column** (P2, M) — instead of hiding collapsed duplicates, show "×N".
  Sketch: extend the collapse logic to count and expose a role.
- **Quick "isolate this" toggle** (P1, S) — one click to filter to the selected line's
  pid+tag, and back.

## Capture & devices

- **★ adb over Wi-Fi / connect by IP** (P1, S) — a field/button to `adb connect host:port`.
  Sketch: `adb/connect.py` wrapper; add to the device bar.
- **★ Custom adb path** (P1, S) — set the `adb` executable path in Settings (for when it's
  not on PATH). Sketch: settings key threaded into `AdbReader`/device calls.
- **Merged multi-device view** (P3, L) — one stream tab combining several devices, tagged
  by serial. Sketch: multiplex readers into one model with a device column.
- **Device status in tab** (P2, S) — show streaming/paused/disconnected state + line count
  in each tab title/icon.
- **Capture dumpsys / bugreport snapshot** (P3, M) — one-shot `adb shell dumpsys …` saved
  alongside the log for context.

## Analysis & insight

- **Timeline histogram** (P2, L) — a thin band charting log volume / error rate over time
  with click-to-seek. Sketch: bucket timestamps; a small custom widget; core bucketing
  is testable.
- **Crash / ANR detector** (P1, M, core-testable) — recognize FATAL/ANR/`beginning of
  crash` patterns and offer jump-to + a badge. Sketch: `core/incidents.py` scans batches;
  status-bar "3 crashes" with next/prev.
- **"Skipped N frames" / jank summary** (P2, M, core-testable) — aggregate Choreographer
  jank into a small report. Sketch: `core/jank.py` regex+sum; a dialog like Tag Summary.
- **Regex named-group extraction → columns** (P3, L) — user regex with named groups adds
  ad-hoc columns. Sketch: `core/extract.py`; dynamic columns in the delegate.

## Appearance & UX

- **Theme editor / more themes** (P2, M) — a few more presets and/or an editor over
  `ui/theme.py` tokens. Sketch: extend `THEMES`; a small editor dialog.
- **Density modes** (P2, S) — compact/comfortable row padding toggle.
- **Font family picker** (P2, S) — choose the monospace family in Settings.
- **Configurable columns** (P2, M) — show/hide + reorder Time/PID/Tag/Process/Level via
  Settings (the delegate already computes widths).

## Export & sharing

- **★ Copy as HTML / rich text** (P2, S, core-testable) — copy selection with level colors
  preserved. Sketch: reuse the HTML exporter for the clipboard.
- **Redaction on export** (P2, M, core-testable) — mask emails/IPs/tokens when saving/
  exporting. Sketch: `core/redact.py` regex set; opt-in checkbox on export.
- **Print / PDF export** (P3, M) — render the visible log to PDF.

## Productivity / integration

- **Bookmark labels & notes** (P2, M) — name a bookmark / attach a note; a bookmarks panel
  to jump between them. Sketch: extend bookmark state to hold text; a dock list.
- **Watch actions** (P2, M) — when a watch pattern hits, optionally play a sound or run a
  command, not just notify. Sketch: extend the watch config.
- **CLI tail mode** (P3, M) — `zlog --tail --filter '…' > out.log` headless. Sketch: an
  argparse path in `app.py` reusing `AdbReader` + `core.query`.

## Quality & performance (cross-cutting)

- **Large-file open progress** (P1, M) — stream a big `.log` in chunks with a progress
  indicator instead of one blocking read.
- **Wrap re-fit on resize** (P1, S) — re-fit wrapped rows when the window/column width
  changes (finish the wrap feature). Sketch: a `resized` signal on `LogTableView` →
  re-layout when wrap is on.
- **Perf smoke tests** (P0-ongoing, M) — a large-capture benchmark in CI to catch
  regressions in append/filter/paint.

## Notes

Most items keep zLog's invariants: put logic in Qt-free `core/` with unit tests, drive the
UI via signals, keep the model virtualized. When we pick one, copy `TEMPLATE.md` to a
focused plan, set it **Approved**, and implement.
