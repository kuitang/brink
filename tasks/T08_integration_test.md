# T08: Integration Test - Full Game with Surplus

## Task ID
T08

## Title
Integration test verifying complete surplus mechanics

## Description
Create comprehensive test that plays a full game and verifies all surplus mechanics work together correctly.

## Blocked By
- T07 (settlement complete)

## Acceptance Criteria
- [ ] Test plays 14-turn game with scripted actions
- [ ] Verifies CC creates surplus with streak bonus
- [ ] Verifies CD/DC captures correct amount
- [ ] Verifies DD burns correct amount
- [ ] Verifies settlement distributes surplus
- [ ] Verifies mutual destruction gives 0,0 VP
- [ ] Verifies final VP includes captured surplus
- [ ] Test passes with current parameter values

## Files to Create
- `tests/integration/test_surplus_mechanics.py`
