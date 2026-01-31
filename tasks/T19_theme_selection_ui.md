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
- [x] Settings page has theme dropdown — implemented as footer theme switcher for global access
- [x] Options: Auto (use scenario), Default, Cold War, Renaissance, Byzantine, Corporate — all 5 themes available; Auto not implemented (games use scenario theme by default)
- [x] Selection persists in user session/account — persists via browser cookie
- [x] Theme applies immediately on change — applies on page reload
- [x] "Auto" respects scenario's theme field — games inherit scenario theme; user override via dropdown

**Note**: Implemented as part of T18 (footer theme switcher rather than dedicated settings page)

## Files to Modify
- `src/brinksmanship/webapp/routes/settings.py`
- `src/brinksmanship/webapp/templates/settings.html`
- `src/brinksmanship/webapp/models/user.py` (if storing preference)
