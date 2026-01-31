# T06: Variance/VP Calculation with Surplus

## Task ID
T06

## Title
Update final VP calculation to include captured surplus

## Description
Modify the variance and VP calculation to incorporate surplus_captured into final scores.

## Blocked By
- T05 (engine tracks surplus)

## Acceptance Criteria
- [x] Final VP = position-based VP + surplus_captured
- [x] Settlement VP includes negotiated surplus split — Note: handled at settlement time
- [x] Mutual destruction = 0 VP for both (not 20)
- [x] Remaining (unsettled) surplus is lost at game end
- [x] Variance calculation unchanged
- [x] Tests verify VP math (TestVPWithCapturedSurplus class)

## Files to Modify
- `src/brinksmanship/engine/variance.py`
- `src/brinksmanship/engine/endings.py`
