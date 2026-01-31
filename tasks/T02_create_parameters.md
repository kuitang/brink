# T02: Create Parameters File

## Task ID
T02

## Title
Create parameters.py with all tunable game balance constants

## Description
Create a single source of truth for all game balance constants. This file must be created BEFORE implementing any mechanics, as all other code will import from it. The parameters should include detailed comments with analysis and tuning guidance.

## Blocked By
- None (foundation task)

## Acceptance Criteria
- [ ] File `src/brinksmanship/parameters.py` exists
- [ ] All parameters from GAME_MANUAL.md Appendix C are defined
- [ ] Each parameter has docstring with:
  - Current value
  - Analysis of what it does
  - Tuning guidance (what to change if X happens)
  - Related parameters that interact with it
- [ ] Parameters are grouped by category:
  - Surplus Creation
  - Exploitation (including streak protection)
  - Risk
  - Settlement (including escalating rejection)
- [ ] File can be imported without circular dependencies
- [ ] Constants use SCREAMING_SNAKE_CASE naming

## Parameters to Include

### Surplus Creation
```python
SURPLUS_BASE = 2.0
SURPLUS_STREAK_BONUS = 0.1
```

### Exploitation
```python
CAPTURE_RATE = 0.4
EXPLOIT_POSITION_GAIN = 0.7
```

### Risk
```python
CC_RISK_REDUCTION = 0.5
EXPLOIT_RISK_INCREASE = 0.8
DD_RISK_INCREASE = 1.8  # Calibrated for <20% mutual destruction rate
DD_BURN_RATE = 0.2
```

### Settlement
```python
REJECTION_BASE_PENALTY = 1.5
REJECTION_ESCALATION = 0.5
SETTLEMENT_MIN_TURN = 5
SETTLEMENT_MIN_STABILITY = 2.0
```

### Reserve Parameters (disabled by default, add if needed)
```python
# STREAK_PROTECTION_RATE = 0.0  # Enable if late-defection dominates
# MAX_PROTECTED_STREAK = 10
```

## Files to Create
- `src/brinksmanship/parameters.py`

## Notes
- See GAME_MANUAL.md Appendix C for full parameter documentation
- Comments in the file should be comprehensive enough for agents to tune
- This file will be modified frequently during balance tuning
