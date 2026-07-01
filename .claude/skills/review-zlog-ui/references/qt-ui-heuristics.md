# zLog UI/UX heuristics

A checklist tuned to zLog: a single-window, mouse-and-keyboard, local desktop tool
for viewing Android logs. Use it to judge each screen. These are lenses, not laws —
when a heuristic doesn't fit a screen, say why rather than forcing it. Skip anything
irrelevant to the screen under review.

## 1. Visual hierarchy
- The log table is the star; it should dominate the window. Toolbar controls are
  supporting and should not crowd or out-weigh it.
- Within a row, severity and message are what users scan for. Check that the Level
  column and the row tint make high-severity lines (E/F) pop without making routine
  lines (I/D) noisy.
- The primary action in the current state should read as primary: when idle, that's
  **Start**; while streaming, **Stop**. The disabled one should clearly look
  disabled (Qt does this by default — confirm it's not overridden).

## 2. Spacing & alignment
- Consistent margins/spacing on the toolbar and around the table. Look for one-off
  spacer values that break rhythm.
- Columns should be sized to their content: fixed/narrow for Time, PID, TID, Level;
  the Message column stretches (`QHeaderView.Stretch`). Check Tag isn't so wide it
  starves Message, and that nothing important is clipped at common window widths.
- Toolbar controls should align on a baseline with even gaps, not ragged.

## 3. Color & contrast
- Row tints (from `ui/theme.py`) must keep text readable in both Light and Dark. Pale yellow/red backgrounds
  with the default near-black text are usually fine — verify contrast, especially if
  a dark theme is added later.
- Semantic color should be consistent: warning = amber, error/fatal = red. Don't
  reuse error-red for a non-error affordance.
- **Don't rely on color alone** to convey severity — the Level column letter
  (W/E/F) carries the same meaning for color-blind users. Keep that column visible.

## 4. Affordances & feedback
- Anything clickable should look clickable. Start/Stop/Clear are buttons — good;
  confirm hover/pressed states aren't flattened away by a custom stylesheet.
- Streaming feedback: when Start is pressed, the user must see it working — the
  status bar line count climbing, rows appearing, Stop enabling. A silent or frozen
  state is a usability bug (and often a threading bug — see the load-bearing note).
- The search box should have placeholder text so its purpose is obvious when empty.
- Error feedback: when `adb` is missing or no device is connected, the `error`
  signal should surface a clear message (status bar or a dialog), not fail silently.

## 5. Empty & edge states
- First launch / before Start: does the user see a helpful empty state ("Press Start
  to stream logcat — make sure a device is connected") rather than a blank grid?
  Empty states are prime onboarding real estate.
- High volume: the table must stay smooth as thousands of rows arrive (this is what
  the virtualized model buys — confirm a review change doesn't defeat it).
- Long content: very long messages/tags shouldn't break row height or layout; check
  elision or wrapping behaves.
- Filtered-to-nothing: when a filter matches no rows, an empty table is acceptable
  but a hint ("No lines match this filter") is friendlier.

## 6. Consistency
- Buttons of the same role look identical. One control style across the toolbar.
- Typography: one family and a small set of sizes/weights. Flag random sizes.
- The Level letters and any glyphs mean the same thing everywhere.

## 7. Layout & responsiveness (desktop sense)
- The window resizes — the table and the stretching Message column should reflow
  sanely; controls shouldn't clip or leave huge dead space. Check narrow and wide.
- Scrolling: the table should scroll smoothly with a usable scrollbar, and
  **autoscroll** should follow new lines only when the user is already at the bottom
  (so scrolling up to read isn't yanked back down). Verify that behavior survives
  any change.

## 8. Keyboard & accessibility
- Desktop users expect keyboard support: Tab order through the toolbar, the search
  box focusable and typable, Esc/closing behaving sanely. Future dialogs should bind
  Enter to submit and Esc to cancel.
- Focus should be visible; disabled controls should look disabled.
- Hit targets: buttons comfortably clickable, not tiny.

## 9. Copy & microcopy
- Button and label text should be specific ("Start", "Clear", "Min level") over
  vague ("OK", "Go"). See the `design:ux-copy` skill for deep copy work.
- Error messages should say what happened and what to do next ("adb not found —
  install Android platform-tools and add it to PATH"), in plain language.
- Consistent capitalization across labels.

## What's load-bearing — don't break it
Per `CLAUDE.md` / `docs/ARCHITECTURE.md`: log lines flow worker-thread →
`batch_ready` signal → main-thread slot → `LogTableModel.append_entries`; never
write to the model/widgets off-thread. The model is **virtualized** (no widget per
row) and filtering goes through `LogFilterProxy` without mutating the master list.
Autoscroll follows new output only when already at the bottom. A UI change must
leave all of these intact.
