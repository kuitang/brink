# T15: CLI Settlement UI

## Task ID
T15

## Title
Implement CLI settlement negotiation interface

## Description
Create the settlement flow in CLI: propose, counter, accept, reject with surplus split.

## Blocked By
- T07 (Settlement mechanics)
- T12 (CLI game loop)

## Acceptance Criteria
- [x] Settlement action available in menu when eligible
- [x] Prompt for VP split (with valid range shown)
- [x] Prompt for surplus split percentage
- [x] Free text argument input via readline
- [x] Show opponent response
- [x] Handle counter-offer flow
- [x] Display rejection penalty warning
- [x] Show escalating risk on rejection (1.5 → 2.25 → 3.0)

## Files to Modify
- `src/brinksmanship/cli/app.py`
