# Brinksmanship Engineering Design

## Overview

Brinksmanship is a game-theoretic strategy simulation where players navigate crises through cooperation, competition, and negotiation. This document describes the **final implementation state**.

**Stack:**
- Python 3.11+, uv package manager
- Flask webapp with htmx, pure CSS theming
- Simple readline-based CLI with `simple-term-menu`
- Claude Agent SDK for LLM opponents and coaching
- SQLite storage

**Entry Points:**
```bash
uv run brinksmanship        # CLI
uv run brinksmanship-web    # Webapp (0.0.0.0:5000)
```

---

## Part I: Core Game Mechanics

### 1.1 Joint Investment Model (Positive-Sum Dynamics)

The game uses a **Joint Investment** model where mutual cooperation creates value:

```
State Variables:
- position_a, position_b (0-10): Relative advantage (hidden from players)
- cooperation_surplus (0-∞): Joint value pool created through cooperation
- surplus_captured_a, surplus_captured_b: VP locked in by each player
- cooperation_streak (0-∞): Consecutive CC outcomes (provides protection)
- risk_level (0-10): Shared escalation measure
- cooperation_score (0-10): Relationship trajectory
- stability (1-10): Behavioral predictability
- turn (1 to max_turns): Current turn (max hidden, 12-16)
```

**Value Creation Rules** (see `src/brinksmanship/parameters.py` for all constants):
```python
CC_outcome:
    # Create new surplus (scales with cooperation streak)
    new_value = SURPLUS_BASE * (1.0 + SURPLUS_STREAK_BONUS * cooperation_streak)
    cooperation_surplus += new_value
    risk_level -= CC_RISK_REDUCTION

CD_outcome (A cooperates, B defects):
    # B captures portion of surplus
    captured = cooperation_surplus * CAPTURE_RATE
    surplus_captured_b += captured
    cooperation_surplus -= captured
    position_b += EXPLOIT_POSITION_GAIN
    position_a -= EXPLOIT_POSITION_GAIN
    risk_level += EXPLOIT_RISK_INCREASE
    # Note: If late-defection dominates, add streak protection (see GAME_MANUAL C.5)

DD_outcome:
    # Mutual defection burns surplus (deadweight loss)
    cooperation_surplus *= (1.0 - DD_BURN_RATE)
    risk_level += DD_RISK_INCREASE
```

**Critical Endings:**
- Risk = 10: **Mutual Destruction** → Both players get **0 VP** (worst outcome)
- This makes avoiding DD critical - it's the path to total loss

**Settlement & Surplus Distribution:**
- Surplus is ONLY distributed through settlement
- If game ends without settlement, remaining surplus is LOST
- This creates strong incentive to negotiate

### 1.2 Scoring System

**Final VP Calculation:**
```python
# Base VP from position ratio
total_pos = position_a + position_b
base_vp_a = (position_a / total_pos) * 100

# Add captured surplus (only from successful exploitation or settlement)
final_vp_a = base_vp_a + surplus_captured_a

# If settled: add share of remaining surplus per agreement
# If not settled: remaining surplus is lost
```

**Multi-Criteria Scorecard (Educational Display):**
```
PERSONAL SUCCESS          PLAYER A    PLAYER B
─────────────────────────────────────────────
Final VP                    72          68
VP Share                   51.4%      48.6%

JOINT SUCCESS                  BOTH
─────────────────────────────────────────────
Total Value Created           140 VP
Value vs Baseline            +40 VP
Pareto Efficiency            87.5%
Settlement Reached?            Yes

BALANCE METRICS (internal)
─────────────────────────────────────────────
Primary: Total Value = VP_A + VP_B
Secondary: VP Spread = |VP_A - VP_B|
```

**Dominant Strategy Test:**
- FAIL if any strategy achieves avg Total Value >120 AND avg VP Share >55%
- This prevents strategies that both grow the pie AND capture disproportionate share

### 1.3 Turn Structure

Each turn follows 8 phases:
1. **Briefing** - Display narrative and shared state
2. **Decision** - Simultaneous action selection
3. **Resolution** - Matrix outcome or special game
4. **State Update** - Update cooperation, stability, surplus
5. **Check Deterministic Endings** - Risk=10, Position=0
6. **Check Crisis Termination** - Turn≥10, Risk>7: P=(Risk-7)×0.08
7. **Check Natural Ending** - Turn = max_turns
8. **Advance** - Increment turn

### 1.4 Settlement Protocol

Available after Turn 4 (unless Stability ≤ 2):
1. Proposer offers VP split + argument text
2. Recipient: ACCEPT / COUNTER / REJECT
3. If COUNTER: proposer responds ACCEPT / FINAL_OFFER
4. Max 3 exchanges, then automatic REJECT
5. Each REJECT adds Risk +1
6. Settlement includes division of cooperation_surplus

---

## Part II: Project Structure

```
src/brinksmanship/
├── parameters.py           # ALL tunable game balance constants (single source of truth)
├── engine/
│   ├── game_engine.py      # Main game loop, turn phases
│   ├── state_deltas.py     # Outcome matrices, surplus mechanics
│   ├── variance.py         # Final resolution with noise
│   ├── resolution.py       # Settlement logic
│   └── endings.py          # Game termination conditions
├── models/
│   ├── state.py            # GameState with cooperation_surplus, streak, captured
│   ├── matrices.py         # 14 matrix type constructors
│   └── actions.py          # Action definitions
├── opponents/
│   ├── base.py             # Opponent interface
│   ├── deterministic.py    # 6 algorithmic opponents
│   ├── historical.py       # 19 LLM personas
│   └── persona_generator.py # Custom persona creation
├── generation/
│   ├── schemas.py          # Scenario Pydantic models
│   ├── scenario_generator.py # LLM scenario generation
│   └── validator.py        # Balance validation
├── testing/
│   ├── game_runner.py      # Single game execution
│   └── batch_runner.py     # Parallel batch testing
├── coaching/
│   └── post_game.py        # LLM coaching analysis
├── storage/
│   └── repository.py       # File/SQLite backends
├── cli/
│   └── app.py              # Simple readline CLI
└── webapp/
    ├── app.py              # Flask factory
    ├── routes/             # Blueprints (auth, game, lobby, etc.)
    ├── services/           # Business logic layer
    ├── models/             # SQLAlchemy models
    ├── templates/          # Jinja2 templates
    └── static/css/         # Era-matched CSS themes
```

---

## Part III: CLI Interface

### 3.1 Technology

- `simple-term-menu` for arrow-key menu navigation
- `readline` module for text input with history
- No Textual dependency

### 3.2 User Flow

```
┌─────────────────────────────────────────┐
│         BRINKSMANSHIP                   │
│                                         │
│  > New Game                             │
│    Load Game                            │
│    Quit                                 │
│                                         │
│  Use arrows to select, Enter to confirm │
└─────────────────────────────────────────┘
```

**Game Screen (text-based):**
```
═══════════════════════════════════════════════════
CUBAN MISSILE CRISIS - Turn 3 vs Tit For Tat
═══════════════════════════════════════════════════

CRISIS STATUS
  Risk: 4.5/10  Cooperation: 6/10  Stability: 7/10
  Surplus Pool: 8.4 VP

BRIEFING
  The blockade is in effect. Soviet ships approach...

CRISIS LOG
  Turn 1: You cooperated, Opponent cooperated (CC) +2.0 surplus
  Turn 2: You cooperated, Opponent cooperated (CC) +2.2 surplus

YOUR ACTIONS
  > 1. [Cooperative] Propose secret negotiations
    2. [Cooperative] Maintain blockade, await response
    3. [Competitive] Demand immediate withdrawal
    4. [Competitive] Prepare air strikes
    5. [Settlement] Propose settlement

Select action (1-5):
```

**Settlement (free text input):**
```
PROPOSE SETTLEMENT
  Suggested VP range: 45-55
  Surplus to distribute: 8.4 VP

  Your VP offer: 52
  Your argument: [free text input with readline]
```

### 3.3 Implementation

```python
# cli/app.py
import readline
from simple_term_menu import TerminalMenu

def main():
    while True:
        menu = TerminalMenu(["New Game", "Load Game", "Quit"])
        choice = menu.show()
        if choice == 0:
            run_new_game()
        elif choice == 1:
            run_load_game()
        else:
            break

def run_game_turn(engine, state):
    # Display state
    print_crisis_status(state)
    print_briefing(engine.get_briefing())
    print_crisis_log(state.history)

    # Action selection
    actions = engine.get_available_actions()
    menu = TerminalMenu([format_action(a) for a in actions])
    choice = menu.show()

    if actions[choice].is_settlement:
        vp, argument = get_settlement_input()
        result = engine.propose_settlement(vp, argument)
    else:
        result = engine.submit_action(actions[choice])

    return result
```

---

## Part IV: Webapp

### 4.1 Architecture

- Flask with blueprints (auth, game, lobby, scenarios, coaching, leaderboard)
- htmx for dynamic updates without JavaScript
- Pure CSS with CSS custom properties for theming
- SQLite database (User, GameRecord models)

### 4.2 Era-Matched CSS Themes

Five distinct visual themes transport players to different historical eras. Each theme is a **complete visual transformation**—not just color swaps, but typography, textures, borders, shadows, and interaction styles.

**Themes:**

| Theme | Era | Character |
|-------|-----|-----------|
| `default` | Timeless | Kingdom of Loathing inspired, serif, earth tones |
| `cold-war` | 1950s-60s | Typewriter fonts, institutional gray, declassified document aesthetic |
| `renaissance` | 15th-16th C | Palatino/Garamond, parchment, gold accents, Medici banking house |
| `byzantine` | Eastern Roman | Uncial-inspired, imperial purple, gold leaf, mosaic hints |
| `corporate` | 2020s | Inter/system sans, pure white, subtle shadows, Silicon Valley boardroom |

**Design Principles:**
- Each theme changes: fonts, colors, borders, shadows, button styles, spacing rhythm
- Themes should feel authentically era-appropriate, not just recolored
- WCAG AA contrast maintained across all themes
- See `tasks/T17_css_era_themes.md` for detailed design specifications

**Implementation:**
- Applied via `<body class="theme-{name}">`
- CSS custom properties for colors, fonts, spacing
- Scenarios specify recommended theme in JSON
- User can override in settings (stored in User.theme_preference)

### 4.3 Routes

| Route | Method | Purpose |
|-------|--------|---------|
| `/` | GET | Games lobby |
| `/new` | GET/POST | New game form |
| `/game/<id>` | GET | Game page |
| `/game/<id>/action` | POST | Submit action (htmx) |
| `/game/<id>/settlement/*` | POST | Settlement flow |
| `/scenarios/` | GET | Scenario browser |
| `/leaderboard/` | GET | Leaderboards |
| `/manual/` | GET | Game rules |
| `/auth/*` | GET/POST | Login/register/logout |

---

## Part V: Testing & Balance

### 5.1 Parameters File

All tunable game balance constants live in `src/brinksmanship/parameters.py`:
- Surplus creation: SURPLUS_BASE, SURPLUS_STREAK_BONUS
- Exploitation: CAPTURE_RATE, STREAK_PROTECTION_RATE, MAX_PROTECTED_STREAK
- Risk: CC_RISK_REDUCTION, EXPLOIT_RISK_INCREASE, DD_RISK_INCREASE, DD_BURN_RATE
- Settlement: REJECTION_BASE_PENALTY, REJECTION_ESCALATION

See GAME_MANUAL.md Appendix C for detailed tuning guidance.

### 5.2 Balance Simulation

```bash
uv run python scripts/balance_simulation.py --games 500 --seed 42
```

**Opponents Tested:**
- NashCalculator, SecuritySeeker, Opportunist
- Erratic, TitForTat, GrimTrigger

**Metrics Collected:**
- Total Value (VP_A + VP_B) - primary balance metric
- VP Share (VP_A / Total) - secondary balance metric
- Settlement rate, mutual destruction rate
- Surplus metrics: pool size at end, capture vs distribute ratio
- Average game length, ending type distribution

**Pass Criteria:**
- No strategy achieves >120 avg Total Value AND >55% avg VP Share
- Variance in 10-40 range
- Settlement rate 30-70%
- **Mutual destruction rate < 20%** (target 10-18%)
- Game length 10-16 turns average

### 5.3 Parameter Tuning Simulations

Before finalizing parameters, run these simulations (see GAME_MANUAL.md Appendix C.5):

1. **Exploitation Timing Analysis**: Find optimal defection turn (should be mid-game)
2. **Streak Protection Sensitivity**: Verify late-game exploitation is balanced
3. **Rejection Penalty Impact**: Tune settlement negotiation tension
4. **Full Balance Validation**: Verify no dominant strategy
5. **Parameter Sweep**: Grid search for optimal configuration

### 5.4 LLM Playtest Infrastructure

Comprehensive playtesting with LLM-based opponents. Each scenario includes pre-defined
historical personas for both sides.

**Scenario Persona Definitions:**

Each scenario JSON includes a `personas` field defining appropriate historical figures:
```json
{
  "scenario_id": "cuban_missile_crisis_1962",
  "personas": {
    "side_a": {
      "persona": "nixon",
      "role_name": "American President",
      "role_description": "Leader of the United States..."
    },
    "side_b": {
      "persona": "khrushchev",
      "role_name": "Soviet Premier",
      "role_description": "Leader of the Soviet Union..."
    }
  }
}
```

**Available Historical Personas:**
- Cold War: nixon, kissinger, khrushchev
- European Diplomacy: bismarck, metternich, richelieu
- Tech Industry: gates, jobs
- Byzantine/Roman: theodora, livia

**Playtest Matchups (3x3 per scenario):**
1. Historical A vs Historical B (period-appropriate figures)
2. Smart Rational Player vs Historical B
3. Historical A vs Smart Rational Player

**Smart Rational Player:**
- Opus 4.5 with explicit game-theoretic knowledge
- Understands surplus mechanics (CC creates, CD captures, DD burns)
- Knows risk management principles
- Makes settlement decisions based on position and risk

**Running Playtests:**
```bash
# Full playtest (10 scenarios × 3 matchups × 3 games = 90 games)
./scripts/playtest/driver.sh --games-per-matchup 3

# Quick test with specific scenarios
./scripts/playtest/driver.sh --games-per-matchup 1 --scenarios cuban_missile_crisis

# Resume interrupted playtest (checks work directory for completed jobs)
./scripts/playtest/driver.sh --work-dir playtest_work
```

**Work Directory Structure:**
```
playtest_work/
├── jobs/           # Job definitions
│   └── all_jobs.txt
├── results/        # JSON results per matchup
│   ├── cuban_missile_crisis__hist_vs_hist.json
│   ├── cuban_missile_crisis__smart_vs_hist_b.json
│   └── ...
└── logs/           # Per-job logs
```

**Report Generation:**
```bash
uv run python scripts/playtest/generate_report.py \
    --work-dir playtest_work \
    --output docs/COMPREHENSIVE_PLAYTEST_REPORT.md
```

### 5.5 Scenario Validation

```bash
uv run python scripts/validate_scenario.py scenarios/cuban_missile_crisis.json
```

Checks:
- ≥8 distinct matrix types
- ≥2 intelligence games
- Valid act/turn structure
- All branch targets exist
- Balance simulation passes
- **Personas defined for both sides**

---

## Part VI: Dependencies

```toml
[project]
dependencies = [
    "claude-agent-sdk>=0.1.0",
    "simple-term-menu>=1.6.0",
    "pydantic>=2.0.0",
    "numpy>=1.24.0",
    "argon2-cffi>=25.1.0",
]

[project.optional-dependencies]
webapp = [
    "flask>=3.0.0",
    "flask-login>=0.6.0",
    "flask-sqlalchemy>=3.1.1",
    "markdown>=3.5.0",
]
dev = [
    "pytest>=7.0.0",
    "pytest-asyncio>=0.21.0",
    "mypy>=1.0.0",
    "ruff>=0.1.0",
]
```

---

## Part VII: Success Criteria

1. **Positive-Sum Mechanics**: Cooperation creates measurable surplus
2. **No Dominant Strategy**: Balance simulation passes with dual metrics
3. **Settlement Incentive**: 30-70% of games end in settlement
4. **CLI Parity**: Full gameplay without accounts
5. **Era Themes**: 5 CSS themes matching scenario categories
6. **Educational Scorecard**: Multi-criteria display after each game
