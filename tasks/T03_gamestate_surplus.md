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
- [ ] `GameState` in `models/state.py` has:
  - `cooperation_surplus: float = 0.0` (shared pool)
  - `surplus_captured_a: float = 0.0` (VP locked by A)
  - `surplus_captured_b: float = 0.0` (VP locked by B)
  - `cooperation_streak: int = 0` (consecutive CC outcomes)
- [ ] All fields serialize/deserialize correctly
- [ ] Existing tests pass
- [ ] New tests verify field initialization

## Files to Modify
- `src/brinksmanship/models/state.py`
