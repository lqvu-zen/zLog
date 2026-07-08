<!--
This is not a standalone deliverable — there is no separate review report file.
Paste this as the "## Findings" section of the plan (docs/plans/ui-<scope>.md,
copied from docs/plans/TEMPLATE.md), right after "## Goal". The plan's own
Scope/Design/Risks/Verification sections follow it and turn the findings you
keep into the actual fix. Delete this comment when you paste it in.
-->

## Findings
**Screens reviewed:** <list> · **Screenshots:** <filenames in run-zlog/screenshots/>

### High
> Hurts usability or looks broken.

#### H1. <short title>
- **Screen / location:** <screen> — `src/zlog/ui/<file>.py:<line>` (or a token in `ui/theme.py`)
- **What & why:** <what's wrong and why it matters to the user>
- **Recommendation:** <concrete, zLog-appropriate fix — this becomes a row in Design>
- **Screenshot:** <filename.png>

### Medium
> Noticeable friction or inconsistency.

#### M1. <short title>
- **Screen / location:** ...
- **What & why:** ...
- **Recommendation:** ...

### Low
> Polish.

#### L1. <short title>
- **Screen / location:** ...
- **What & why:** ...
- **Recommendation:** ...

### What already works well
<Patterns worth preserving — consistency, good states, clear hierarchy — so
whoever implements the plan knows what NOT to touch.>

### Deferred
<Findings you're deliberately not fixing in this plan (e.g. out of scope, needs
its own design pass) — carry them here instead of silently dropping them, and
say why. A deferred High/Medium finding should usually become a Backlog line in
docs/ROADMAP.md or a new Draft plan of its own.>
