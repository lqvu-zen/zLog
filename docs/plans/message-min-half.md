# Plan: Guarantee the message ≥ 50% of the row

- **Status:** Done
- **Owner:** unassigned
- **Created:** 2026-07-14
- **Related:** [fixed-columns-middle-elide.md](fixed-columns-middle-elide.md), [process-name-column.md](process-name-column.md)

## Requirement

Time, PID-TID and Level are fixed and always shown in full. Tag and the optional
Process column may be truncated (middle-elide) so the **message keeps at least 50%**
of the row width.

## Fix

The delegate lays out width-aware: after reserving the fixed columns, Tag + Process
share a budget = `usable − fixed − 0.5·usable`. When their natural widths fit the
budget they're used as-is (message gets the rest, ≥50%); otherwise they scale down
proportionally and middle-elide, holding the message at exactly 50%.

Extracted as a pure `plan_tag_proc_widths(usable, cw, show)` so the guarantee is
unit-tested. `seg()` now takes pixel widths.

Note: on a window so narrow that Time+PID+Level alone exceed half the width, the
message can't reach 50% without shrinking those fixed columns (which must stay
full) — the flexible columns collapse to 0 first. At normal widths the message is
≥50%.

## Verification

- [x] `uv run pytest` (240; new `tests/test_log_delegate.py`)
- [x] ruff clean
- [x] message ≥50% at 1000/1400/1920px; Tag/Process natural on wide, shrink on narrow.
