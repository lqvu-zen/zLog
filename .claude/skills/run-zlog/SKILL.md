---
name: run-zlog
description: Launch the zLog desktop app and capture screenshots of its running UI, including headlessly (no physical display). Use this whenever you need to SEE zLog running — to smoke-test that the app still launches and renders after a change, to capture a specific UI state, or to provide the screenshots the review-zlog-ui skill judges. Trigger when the user says "run the app", "does it still launch", "show me what it looks like", "take a screenshot", or when another skill needs a visual of a given state. Do NOT use it to design-review the UI (use review-zlog-ui) or to add a feature (use add-zlog-feature).
---

# Running & screenshotting zLog

zLog is a PySide6 (Qt) app. You can't judge or verify its UI from source alone, and
you often don't have a real display. This skill's driver solves both: it launches
the app and writes a PNG of the window using `QWidget.grab()`, which paints the
widget tree to a pixmap and therefore works under Qt's **offscreen** platform.

## The driver

`scripts/driver.py` lives in this skill. Run it from the project root:

```bash
uv run --with pillow python .claude/skills/run-zlog/scripts/driver.py <scenario>
```

It auto-selects `QT_QPA_PLATFORM=offscreen` when no display is present (Linux/CI),
so it works without a screen. On a normal desktop it renders with the real platform.
Screenshots are written to `.claude/skills/run-zlog/screenshots/`. Read them with the
`Read` tool.

The driver seeds the table with **sample log lines directly into the model**, so it
needs **no connected device and no running `adb`** — it exercises the UI, not the
data source.

## Scenarios

| Scenario | What it shows |
|---|---|
| `smoke` (default) | idle, empty window — confirms the app launches and lays out |
| `populated` | table seeded with sample lines across levels (I/D/W/E/F + a banner) |
| `filtered` | seeded, then min level set to Warning — shows the proxy filtering |

## Adding a scenario

The driver holds the live app objects, so you can reach any state programmatically:

- `window.model.append_entries([...])` — seed rows (build `LogEntry` from
  `zlog.core.models`).
- `window.proxy.set_min_level("W")` / `window.proxy.set_text("...")` — drive filters.
- `window.search.setText("...")` — type into the search box.

Copy an existing `scenario_*` function, drive the widgets to the state you want,
call `_shot(window, "<name>")`, and register it in the `SCENARIOS` dict. Keep one
screenshot per state with a descriptive name.

## When you actually want the real stream

The driver intentionally avoids `adb` so it's deterministic. To smoke-test the real
pipeline (reader thread → signal → model) you need a device/emulator and `adb` on
PATH, then just launch normally:

```bash
uv run zlog
```

## Verification etiquette

A screenshot is only verification if you **read it**. After running a scenario, open
the PNG and confirm what you claim. If the environment can't render at all (rare —
offscreen usually works), say so plainly rather than asserting the UI looks fine.
Screenshots are throwaway artifacts: don't commit `screenshots/` (it's gitignored).
