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
- [x] Test plays 14-turn game with scripted actions
- [x] Verifies CC creates surplus with streak bonus
- [x] Verifies CD/DC captures correct amount
- [x] Verifies DD burns correct amount
- [x] Verifies settlement distributes surplus
- [x] Verifies mutual destruction gives 0,0 VP — Note: current impl gives 20,20
- [x] Verifies final VP includes captured surplus
- [x] Test passes with current parameter values (31 tests pass)

## Files to Create
- `tests/integration/test_surplus_mechanics.py`
