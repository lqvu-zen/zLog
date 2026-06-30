---
name: review-zlog-ui
description: Review and improve the zLog desktop app's UI and UX. Use this whenever the user wants a design/usability review of zLog, mentions the app "looks off," wants feedback on layout, spacing, colors, contrast, visual hierarchy, affordances, empty states, or accessibility — or asks to polish, clean up, modernize, or improve the look and feel of any zLog screen (the log table, toolbar, level/search controls, status bar, future dialogs). Trigger even when the user doesn't say the words "UI" or "UX" but is clearly asking whether a screen is good, what to fix, or to make it nicer. Produces a prioritized findings report, then an approved plan in docs/plans/, then concrete edits to src/zlog/ui/*. Do NOT use it for adding features (use add-zlog-feature) or just launching the app (use run-zlog).
---

# Reviewing & improving zLog UI/UX

zLog is a **PySide6 (Qt) desktop app** for viewing Android `adb logcat`. Its entire
interface lives in `src/zlog/ui/`. A good review combines two things neither alone
gives you: **what the app actually looks like when running** (screenshots) and
**why it looks that way** (the source). Gather both, judge against the heuristics
below, then propose fixes that respect the app's existing design language instead
of importing generic web-design advice that doesn't fit a native desktop tool.

zLog is **plan-first**: a review may end in code changes, and those changes — like
any change — need an approved plan in `docs/plans/` before they're written (see
phase 5 and `docs/plans/README.md`).

## Where the UI lives

| Concern | File |
|---|---|
| Main window, toolbar, controls, wiring, autoscroll | `src/zlog/ui/main_window.py` |
| Table model, filter proxy, **level row colors (`LEVEL_COLOR`)**, columns | `src/zlog/ui/log_model.py` |
| App bootstrap / where a global stylesheet would go | `src/zlog/app.py` |

**Colors are currently centralized in `LEVEL_COLOR`** (in `log_model.py`). Before
recommending any color change, read it and refer to entries by meaning (warning /
error / fatal). Never hard-code a hex value into a widget when a token exists or
should exist — if the palette is growing, recommend introducing a single
`src/zlog/ui/theme.py` and migrating tokens there, so the palette stays the one
source of truth. Keep typography consistent (Qt's default application font unless a
deliberate choice is made and applied app-wide in `app.py`).

## The review workflow

### 1. See the app running

You cannot review look-and-feel from source alone — spacing, contrast, alignment,
and crowding only reveal themselves on screen. Use the **`run-zlog` skill**, whose
driver launches the app, optionally drives a scenario, and saves a PNG of the
window. It works **headlessly** (it renders via `widget.grab()` under
`QT_QPA_PLATFORM=offscreen`), so no physical display is required:

```bash
uv run --with pillow python .claude/skills/run-zlog/scripts/driver.py smoke
```

Screenshots land in `.claude/skills/run-zlog/screenshots/`. Read them with the
`Read` tool. Capture whatever states are relevant: the **idle/empty window**, the
table **populated with sample log lines** (the driver can seed the model directly
without a device), and the effect of a **level filter** and a **text filter**. If
the user points at a specific screen, prioritize it. If no scenario reaches the
state you need, add one — copy an existing `_scenario(...)` in `driver.py`, seed the
model or toggle the proxy, then `_shot(...)`, and add a branch in `main()`.

If the app genuinely can't be rendered in the current environment, say so plainly
and fall back to a source-only review — but flag that visual issues (crowding,
contrast, alignment) are harder to catch that way, and read any recent screenshots
already in the `run-zlog/screenshots/` folder.

### 2. Read the relevant source

For each screen under review, read the file(s) that build it. You're looking for the
*structural causes* of what you see: layout margins/spacing, `addWidget` stretch
factors, column resize modes, header visibility, the `LEVEL_COLOR` choices,
selection behavior, placeholder text, disabled states. A finding is only actionable
if you can point to the line that produces it.

### 3. Judge against the heuristics

Read `references/qt-ui-heuristics.md` and evaluate each screen against it. The
heuristics are tuned to zLog — a single-window, keyboard-and-mouse, local desktop
log viewer — not a mobile app or a website. Don't apply web conventions that don't
belong here.

### 4. Write the findings report

Use the template in `assets/report-template.md`. The core of a useful report is
**prioritized, located, justified** findings:

- **Severity** — `High` (hurts usability or looks broken), `Medium` (noticeable
  friction or inconsistency), `Low` (polish).
- **Location** — the screen and the exact `file:line` (or token name) responsible.
- **What & why** — what's wrong and *why it matters to the user*, not just "this
  violates a rule."
- **Recommendation** — a concrete, zLog-appropriate fix.

Order findings by severity. Lead with a 2–3 sentence summary so the user gets the
gist before the details. Reference screenshots by filename. Save the report to the
outputs folder (or the project root if the user prefers) as a markdown file. A pure
review that the user only wants as feedback can stop here.

### 5. Turn the accepted fixes into a plan — in `docs/plans/` — and get it approved

If the user wants the fixes applied, **don't edit code yet.** Capture the High/Medium
fixes you'll make as a plan first (the same plan-first gate the `add-zlog-feature`
skill uses):

- Copy `docs/plans/TEMPLATE.md` to `docs/plans/ui-<scope>.md` (e.g. `ui-table-polish.md`).
- Fill in **Scope** (which findings are in, which are deferred), **Design** (the
  `src/zlog/ui/*` files and lines, color tokens added to `LEVEL_COLOR` or a new
  `theme.py`), **Risks** (must not break threading, virtualization, proxy filtering,
  or autoscroll-at-bottom), and **Verification** (which `run-zlog` scenarios you'll
  re-shoot). Split a big redesign into several plan files by area.
- Add a row in `docs/plans/README.md`, set **Status: Draft**, show it to the user,
  and set **Status: Approved** once they're on board.

### 6. Propose and make the edits

Set the plan **Status: In progress**. Prefer **small, surgical diffs** that respect
existing patterns:

- Route colors through `LEVEL_COLOR` (or a new `theme.py`); never hard-code hex at a
  widget.
- Preserve behavior that is load-bearing: the worker-thread to signal to slot output
  path, the virtualized model (`append_entries`, no per-row widgets), proxy-based
  filtering, and autoscroll-only-when-at-bottom. A visual change must not break
  threading, virtualization, or layout.
- Show edits as a clear before/after, grouped by file. Don't bundle unrelated
  refactors into a UI pass.

After editing, **re-run the relevant `run-zlog` scenario and screenshot again** to
verify the change actually looks better and didn't break the layout. Reading the new
screenshot is the verification step — don't claim an improvement you haven't looked
at. Tick the plan's Verification boxes, set **Status: Done**, and commit the plan
file alongside the UI changes.

## Tone

Be a candid, constructive design reviewer. The goal is a better app, so don't pad
findings with false praise, but do note what already works well — consistency and
clear patterns are worth preserving, and the user needs to know what *not* to touch.
Explain the reasoning behind each recommendation so the user can make their own call
rather than following orders blindly.
