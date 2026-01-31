# T20: Webapp Educational Scorecard

## Task ID
T20

## Title
Display multi-criteria scorecard at game end in webapp

## Description
Show the educational scorecard from GAME_MANUAL.md Section 4.4 styled for webapp.

## Blocked By
- T14 (Webapp surplus display)

## Acceptance Criteria
- [x] Game end page shows scorecard
- [x] Personal Success section: Final VP, VP Share
- [x] Joint Success section: Total Value, vs Baseline, Pareto Efficiency
- [x] Settlement info: reached?, surplus distributed, terms
- [x] Strategic Profile: max streak, times exploited, who initiated settlement
- [x] Styled appropriately per active theme
- [x] "Play Again" and "Return to Lobby" buttons

## Files to Modify
- `src/brinksmanship/webapp/templates/game_end.html`
- `src/brinksmanship/webapp/routes/game.py`
