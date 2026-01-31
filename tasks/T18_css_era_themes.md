# T18: CSS Era Themes

## Task ID
T18

## Title
Create 5 distinct CSS themes for webapp

## Description
Implement the era-matched CSS themes from ENGINEERING_DESIGN.md. Each theme should feel authentically era-appropriate.

## Blocked By
- T14 (Webapp surplus display)

## Acceptance Criteria
- [x] 5 themes implemented:
  - `default`: Kingdom of Loathing inspired, serif, earth tones
  - `cold-war`: Typewriter fonts, institutional gray, declassified document
  - `renaissance`: Palatino/Garamond, parchment, gold accents
  - `byzantine`: Uncial-inspired, imperial purple, gold leaf
  - `corporate`: Inter/system sans, pure white, subtle shadows
- [x] Applied via `<body class="theme-{name}">`
- [x] CSS custom properties for colors, fonts, spacing
- [x] WCAG AA contrast maintained
- [x] All game elements styled consistently per theme

**Note**: Also includes theme switcher in footer (T19 functionality)

## Files to Modify
- `src/brinksmanship/webapp/static/css/style.css`
- `src/brinksmanship/webapp/templates/base.html`
