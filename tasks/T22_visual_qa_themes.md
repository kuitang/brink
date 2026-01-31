# T22: Visual QA Themes

## Task ID
T22

## Title
Visually test all 5 themes using Playwright screenshots

## Description
Perform visual quality assurance on all theme implementations by capturing screenshots of key pages in each theme. Verify that themes render correctly, maintain readability, and provide distinct visual identities. This ensures the theming system works across all pages and that no visual bugs were introduced.

## Blocked By
- T17 (CSS era themes - themes must exist)
- T18 (Theme selection UI - must be able to switch themes)
- T19 (Webapp scorecard - game over page must be complete)

## Acceptance Criteria
- [x] Screenshots captured for all 5 themes: default, cold-war, renaissance, byzantine, corporate
- [x] Each theme tested on 6 pages: login, lobby, new game, game play, game over, manual
- [x] Total of 30 screenshots (5 themes x 6 pages)
- [x] All themes maintain text readability (no contrast issues)
- [x] No visual bugs: broken layouts, missing styles, overlapping elements
- [x] Theme colors apply consistently across all components
- [x] Accent colors visible on interactive elements (buttons, links)
- [x] Surplus display and scorecard render correctly in all themes
- [x] Screenshots saved with naming convention: `{theme}-{page}.png`
- [x] Visual comparison confirms each theme is distinct

**Script**: `scripts/visual_qa_themes.py` - automated Playwright screenshot capture

## Files to Modify
- Create `scripts/visual_qa_themes.py` - Playwright test script for automated screenshots
- Screenshots saved to `qa_screenshots/` directory (gitignored)

## Test Procedure
```
1. Start webapp: uv run brinksmanship-web
2. For each theme:
   a. Login as test user
   b. Set theme preference
   c. Navigate to each page and capture screenshot
   d. Verify no console errors
3. Compare screenshots for visual correctness
4. Document any issues found
```
