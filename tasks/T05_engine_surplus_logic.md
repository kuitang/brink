# T05: Engine Surplus Creation/Capture Logic

## Task ID
T05

## Title
Integrate surplus mechanics into GameEngine

## Description
Update the game engine to apply surplus changes from state_deltas and track cooperation_streak correctly.

## Blocked By
- T04 (state_deltas has surplus mechanics)

## Acceptance Criteria
- [ ] `GameEngine.submit_actions()` updates surplus fields
- [ ] CC outcome increments streak, applies surplus creation
- [ ] CD/DC outcome resets streak, applies capture
- [ ] DD outcome resets streak, applies burn
- [ ] Surplus changes visible in ActionResult
- [ ] Integration tests verify full turn cycle

## Files to Modify
- `src/brinksmanship/engine/game_engine.py`
