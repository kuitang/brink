# Claude Code Instructions

## Required Reading

**CRITICAL**: Before starting any task, read `GAME_MANUAL.md` in the project root. This document contains the authoritative game rules and mechanics. All implementation must conform to this specification.

Estimated tokens: ~10,000 tokens (44KB, 6600 words - worth the context cost for correctness)

## Document Hierarchy

**IF YOU FIND A CONTRADICTION BETWEEN DOCUMENTS, FLAG IT LOUDLY** in your response so it can be fixed. However, when proceeding with implementation:

1. **GAME_MANUAL.md** is the authoritative source for all game mechanics, formulas, and numeric parameters
2. **ENGINEERING_DESIGN.md** is secondary - it describes implementation approach but defers to GAME_MANUAL.md for game rules
3. If ENGINEERING_DESIGN.md contradicts GAME_MANUAL.md, follow GAME_MANUAL.md and flag the inconsistency

---

## Code Style

### Imports
- All imports must be at the top of the file
- No inline imports inside functions or methods
- Group imports: stdlib, third-party, local

### Exception Handling
- Do NOT add try/except blocks unless you have a meaningful alternative action
- Let exceptions propagate naturally
- Only catch exceptions when you can actually recover or need to transform the error
- "Log and continue" is not a valid recovery strategy

### General
- Avoid over-engineering
- No defensive programming against impossible states
- Trust internal code; only validate at system boundaries

## Webapp

### Launching the Webapp

```bash
# Install webapp dependencies
uv sync --extra webapp

# Generate the game manual HTML (required before first run, and after GAME_MANUAL.md changes)
uv run python scripts/generate_manual.py

# Start the webapp (listens on 0.0.0.0:5000)
uv run brinksmanship-web
```

The webapp listens on `0.0.0.0:5000` by default for network accessibility.

### Generated Files

The game manual page (`/manual`) is generated from `GAME_MANUAL.md`. The generated HTML is stored in `src/brinksmanship/webapp/templates/generated/` (gitignored). Regenerate after any changes to `GAME_MANUAL.md`.

### htmx
**CRITICAL**: Always use the latest version of htmx. Check https://htmx.org for the current version before downloading or referencing. Do NOT use outdated CDN links or old versions from examples.

## Textual CLI

### Launching the CLI

```bash
uv run brinksmanship
```

### Testing Textual UI Programmatically

Use Textual's pilot for headless testing. This enables programmatic navigation and screenshot capture:

```python
from brinksmanship.cli.app import BrinksmanshipApp, GameScreen
import asyncio

async def test():
    app = BrinksmanshipApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()

        # Navigate using clicks and keypresses
        await pilot.click('#new-game')
        await pilot.pause(0.3)
        await pilot.press('down')
        await pilot.press('enter')

        # Take SVG screenshot
        svg = app.export_screenshot()
        with open('/tmp/screenshot.svg', 'w') as f:
            f.write(svg)

        # Check widget sizes
        widget = app.screen.query_one('#some-widget')
        print(f'Size: {widget.size.width}x{widget.size.height}')

        # Read widget content
        print(app.screen.query_one('#widget-id').render())

asyncio.run(test())
```

Run with: `timeout 20 uv run python -c "..."`

### Converting SVG Screenshots to PNG

Use cairosvg (install with `uv add cairosvg` if needed):

```python
import cairosvg
cairosvg.svg2png(url='/tmp/screenshot.svg', write_to='/tmp/screenshot.png')
```

Or serve SVG via HTTP and use Playwright MCP to screenshot:

```bash
cd /tmp && python3 -m http.server 8765 &
# Then use browser_navigate to http://localhost:8765/screenshot.svg
# Then use browser_take_screenshot
```

### Debug Mode

For interactive debugging with Textual devtools:

```bash
# Terminal 1: Start the console
textual console

# Terminal 2: Run with dev flag
textual run --dev src/brinksmanship/cli/app.py
```

Or set `TEXTUAL=1` environment variable for basic logging.

## E2E Testing

### Balance Simulation

The balance simulation verifies game balance by running automated strategy matchups. It imports actual game parameters from `state_deltas.py` to ensure simulation matches real game behavior.

```bash
# Run balance simulation (500 games per pairing)
uv run python scripts/balance_simulation.py --games 500 --seed 42

# Quick test (100 games)
uv run python scripts/balance_simulation.py --games 100
```

**Key metrics to verify:**
- No dominant strategy (>60% win rate)
- Reasonable mutual destruction rate (15-30%)
- Position eliminations working
- Resource eliminations should be 0 (resources removed from game)

### Webapp E2E Testing with Playwright MCP

Use Playwright MCP for browser-based E2E testing:

```
1. Start webapp: uv run brinksmanship-web
2. Use browser_navigate to http://localhost:5000
3. Use browser_fill_form to register/login
4. Use browser_click to navigate and interact
5. Use browser_snapshot to verify UI state
6. Use browser_take_screenshot for visual verification
```

**Critical UI verifications:**
- **Positions are NOT visible** - game board should show "Crisis Status" only
- **Resources are NOT visible** - removed from game
- **Crisis Log** shows action history with cooperate/compete labels
- **Briefing** displays scenario narrative

Example Playwright test flow:
```
1. Navigate to localhost:5000
2. Register user (e2etest / testpass123)
3. Login
4. Click "Start New Game"
5. Select scenario (e.g., Cuban Missile Crisis)
6. Select opponent (e.g., Tit For Tat)
7. Click "Start Game"
8. Verify: Crisis Status shows Risk/Cooperation/Stability/Turn
9. Verify: NO Position or Resources displayed
10. Take action, verify Crisis Log updates
```

### CLI Testing

Quick CLI smoke test:
```bash
# Test CLI launches (times out after 5 seconds)
timeout 5 uv run brinksmanship || true
```

For headless CLI testing, use Textual pilot (see "Testing Textual UI Programmatically" above).
