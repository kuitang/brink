# T17: Update All Scenarios with Themes

## Task ID
T17

## Title
Add theme field to all 10 scenario JSON files

## Description
Update each scenario file to include an appropriate CSS theme based on its historical era.

## Blocked By
- T13 (Scenario schema has theme field)

## Acceptance Criteria
- [ ] All scenarios in `scenarios/` have theme field
- [ ] Theme assignments:
  - Cuban Missile Crisis → cold-war
  - Berlin Blockade → cold-war
  - Medieval scenarios → renaissance
  - Ancient/Byzantine → byzantine
  - Modern/corporate → corporate
  - Generic → default
- [ ] All scenarios validate against schema
- [ ] Scenario generator uses theme field

## Files to Modify
- `scenarios/*.json` (all scenario files)
