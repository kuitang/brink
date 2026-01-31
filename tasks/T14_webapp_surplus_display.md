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
- [x] Game page shows "Surplus Pool: X VP"
- [x] Shows "Your Captured: X VP" and "Opponent Captured: X VP"
- [x] Shows cooperation streak count (color-coded)
- [x] Updates via htmx after each turn
- [x] Clear visual hierarchy (blue pool, green captured, red opponent)

## Files to Modify
- `src/brinksmanship/webapp/templates/game.html`
- `src/brinksmanship/webapp/routes/game.py`
