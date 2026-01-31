# T07: Settlement with Surplus Split and Escalating Rejection

## Task ID
T07

## Title
Update settlement to distribute surplus and apply escalating rejection penalty

## Description
Settlement must now negotiate both VP split AND surplus split. Rejection penalty escalates per REJECTION_BASE_PENALTY and REJECTION_ESCALATION.

## Blocked By
- T06 (VP calculation includes surplus)

## Acceptance Criteria
- [ ] Settlement proposal includes surplus percentage split
- [ ] Accepted settlement distributes surplus per agreement
- [ ] Rejection adds escalating risk: `base * (1 + escalation * (n-1))`
- [ ] 3 rejections end negotiation
- [ ] Constants from parameters.py used
- [ ] Tests verify rejection escalation math

## Files to Modify
- `src/brinksmanship/engine/resolution.py`
