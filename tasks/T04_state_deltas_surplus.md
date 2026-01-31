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
- [x] CC outcome creates surplus: `SURPLUS_BASE * (1 + SURPLUS_STREAK_BONUS * streak)`
- [x] CD/DC outcome captures surplus: `surplus * CAPTURE_RATE`
- [x] DD outcome burns surplus: `surplus *= (1 - DD_BURN_RATE)`
- [x] Risk changes use constants from parameters.py
- [x] All 14 matrix types updated — Note: surplus mechanics apply uniformly via `apply_surplus_effects()` function
- [x] Unit tests verify surplus math (5 tests in TestSurplusMechanics class)

## Files to Modify
- `src/brinksmanship/engine/state_deltas.py`
