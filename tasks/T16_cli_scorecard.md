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
- [x] Display Personal Success: Final VP, VP Share
- [x] Display Joint Success: Total Value, vs Baseline, Pareto Efficiency
- [x] Display settlement info: reached?, surplus distributed
- [x] Display Strategic Profile: max streak, times exploited
- [x] ASCII table formatting
- [x] Wait for keypress before returning to menu

## Files to Modify
- `src/brinksmanship/cli/app.py`
