# T19: Theme Selection UI

## Task ID
T19

## Title
Add theme selection to webapp settings

## Description
Allow users to override scenario's recommended theme with their preference.

## Blocked By
- T18 (CSS themes exist)

## Acceptance Criteria
- [ ] Settings page has theme dropdown
- [ ] Options: Auto (use scenario), Default, Cold War, Renaissance, Byzantine, Corporate
- [ ] Selection persists in user session/account
- [ ] Theme applies immediately on change
- [ ] "Auto" respects scenario's theme field

## Files to Modify
- `src/brinksmanship/webapp/routes/settings.py`
- `src/brinksmanship/webapp/templates/settings.html`
- `src/brinksmanship/webapp/models/user.py` (if storing preference)
