# T12: CLI Game Loop

## Task ID
T12

## Title
Implement CLI turn-by-turn game loop

## Description
Create the main game loop displaying state, accepting actions, and showing results.

## Blocked By
- T05 (Engine surplus logic)
- T11 (CLI scaffolding)

## Acceptance Criteria
- [ ] Display crisis status: Risk, Cooperation, Stability, Surplus Pool
- [ ] Display briefing text from scenario
- [ ] Display turn history (outcome per turn)
- [ ] Action selection via menu
- [ ] Show outcome after each turn
- [ ] Loop until game ends
- [ ] Handle all ending types

## Files to Modify
- `src/brinksmanship/cli/app.py`
