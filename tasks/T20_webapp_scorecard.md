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
- [ ] Game end page shows scorecard
- [ ] Personal Success section: Final VP, VP Share
- [ ] Joint Success section: Total Value, vs Baseline, Pareto Efficiency
- [ ] Settlement info: reached?, surplus distributed, terms
- [ ] Strategic Profile: max streak, times exploited, who initiated settlement
- [ ] Styled appropriately per active theme
- [ ] "Play Again" and "Return to Lobby" buttons

## Files to Modify
- `src/brinksmanship/webapp/templates/game_end.html`
- `src/brinksmanship/webapp/routes/game.py`
