# T04: State Deltas with Surplus Mechanics

## Task ID
T04

## Title
Update state_deltas.py to implement surplus creation, capture, and burn

## Description
Modify the outcome effect system to implement the Joint Investment model from GAME_MANUAL.md. Use constants from parameters.py.

## Blocked By
- T03 (GameState has surplus fields)

## Acceptance Criteria
- [ ] CC outcome creates surplus: `SURPLUS_BASE * (1 + SURPLUS_STREAK_BONUS * streak)`
- [ ] CD/DC outcome captures surplus: `surplus * CAPTURE_RATE`
- [ ] DD outcome burns surplus: `surplus *= (1 - DD_BURN_RATE)`
- [ ] Risk changes use constants from parameters.py
- [ ] All 14 matrix types updated
- [ ] Unit tests verify surplus math

## Files to Modify
- `src/brinksmanship/engine/state_deltas.py`
