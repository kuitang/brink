# T03: Add Surplus Fields to GameState

## Task ID
T03

## Title
Add cooperation_surplus, surplus_captured, and cooperation_streak to GameState

## Description
Extend the GameState model to track the Joint Investment mechanics. This is the foundation for all surplus-based gameplay.

## Blocked By
- T01 (Delete obsolete docs)
- T02 (parameters.py exists)

## Acceptance Criteria
- [x] `GameState` in `models/state.py` has:
  - `cooperation_surplus: float = 0.0` (shared pool)
  - `surplus_captured_a: float = 0.0` (VP locked by A)
  - `surplus_captured_b: float = 0.0` (VP locked by B)
  - `cooperation_streak: int = 0` (consecutive CC outcomes)
- [x] All fields serialize/deserialize correctly
- [x] Existing tests pass
- [x] New tests verify field initialization

**Note**: Added convenience properties `total_surplus_captured` and `surplus_remaining`. Updated `apply_action_result` to preserve surplus fields.

## Files to Modify
- `src/brinksmanship/models/state.py`
