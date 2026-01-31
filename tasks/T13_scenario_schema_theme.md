# T13: Scenario Schema Theme Field

## Task ID
T13

## Title
Add theme field to scenario schema

## Description
Update the scenario JSON schema to include a recommended CSS theme.

## Blocked By
- T07 (Settlement complete - core mechanics done)

## Acceptance Criteria
- [ ] `ScenarioSchema` has `theme: str` field
- [ ] Valid themes: default, cold-war, renaissance, byzantine, corporate
- [ ] Schema validation accepts theme field
- [ ] Missing theme defaults to "default"

## Files to Modify
- `src/brinksmanship/generation/schemas.py`
