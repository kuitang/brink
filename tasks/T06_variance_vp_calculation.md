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
- [ ] Final VP = position-based VP + surplus_captured
- [ ] Settlement VP includes negotiated surplus split
- [ ] Mutual destruction = 0 VP for both (not 20)
- [ ] Remaining (unsettled) surplus is lost at game end
- [ ] Variance calculation unchanged
- [ ] Tests verify VP math

## Files to Modify
- `src/brinksmanship/engine/variance.py`
- `src/brinksmanship/engine/endings.py`
