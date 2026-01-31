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
- [ ] Settlement action available in menu when eligible
- [ ] Prompt for VP split (with valid range shown)
- [ ] Prompt for surplus split percentage
- [ ] Free text argument input via readline
- [ ] Show opponent response
- [ ] Handle counter-offer flow
- [ ] Display rejection penalty warning
- [ ] Show escalating risk on rejection

## Files to Modify
- `src/brinksmanship/cli/app.py`
