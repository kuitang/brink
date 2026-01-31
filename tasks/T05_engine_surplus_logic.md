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
- [x] `GameEngine.submit_actions()` updates surplus fields
- [x] CC outcome increments streak, applies surplus creation
- [x] CD/DC outcome resets streak, applies capture
- [x] DD outcome resets streak, applies burn
- [x] Surplus changes visible in ActionResult — Note: visible through state changes
- [x] Integration tests verify full turn cycle (4 tests in TestSurplusMechanics)

## Files to Modify
- `src/brinksmanship/engine/game_engine.py`
