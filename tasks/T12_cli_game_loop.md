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
- [x] Display crisis status: Risk, Cooperation, Stability, Surplus Pool
- [x] Display briefing text from scenario
- [x] Display turn history (outcome per turn)
- [x] Action selection via menu
- [x] Show outcome after each turn
- [x] Loop until game ends
- [x] Handle all ending types

## Files to Modify
- `src/brinksmanship/cli/app.py`
