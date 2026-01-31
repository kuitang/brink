# T16: CLI Educational Scorecard

## Task ID
T16

## Title
Display multi-criteria scorecard at game end in CLI

## Description
Show the educational scorecard from GAME_MANUAL.md Section 4.4 after each game.

## Blocked By
- T15 (CLI settlement UI)

## Acceptance Criteria
- [ ] Display Personal Success: Final VP, VP Share
- [ ] Display Joint Success: Total Value, vs Baseline, Pareto Efficiency
- [ ] Display settlement info: reached?, surplus distributed
- [ ] Display Strategic Profile: max streak, times exploited
- [ ] ASCII table formatting
- [ ] Wait for keypress before returning to menu

## Files to Modify
- `src/brinksmanship/cli/app.py`
