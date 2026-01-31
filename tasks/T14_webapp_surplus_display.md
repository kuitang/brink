# T14: Webapp Surplus Display

## Task ID
T14

## Title
Display surplus information in webapp game view

## Description
Update webapp templates to show cooperation surplus, captured amounts, and streak.

## Blocked By
- T07 (Settlement complete)

## Acceptance Criteria
- [ ] Game page shows "Surplus Pool: X VP"
- [ ] Shows "Your Captured: X VP" and "Opponent Captured: X VP"
- [ ] Shows cooperation streak count
- [ ] Updates via htmx after each turn
- [ ] Clear visual hierarchy

## Files to Modify
- `src/brinksmanship/webapp/templates/game.html`
- `src/brinksmanship/webapp/routes/game.py`
