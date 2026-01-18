# Brinksmanship: Engineering Design Document

## Implementation Guide for Claude Code

---

## Overview

This document provides a step-by-step implementation plan for building Brinksmanship, a game-theoretic strategy simulation. The implementation uses Python with the Claude Agent SDK for all LLM tasks.

**Target Runtime**: Python 3.11+
**LLM Integration**: Claude Agent SDK (claude-agent-sdk)
**CLI Framework**: Textual
**Configuration**: All prompts stored in `prompts.py`

---

## Project Structure

```
brinksmanship/
├── README.md
├── pyproject.toml
├── GAME_MANUAL.md                    # Authoritative rules reference
├── src/
│   └── brinksmanship/
│       ├── __init__.py
│       ├── prompts.py                # All LLM prompts
│       ├── models/
│       │   ├── __init__.py
│       │   ├── state.py              # Game state dataclasses
│       │   ├── actions.py            # Action definitions
│       │   └── matrices.py           # Game theory matrix definitions
│       ├── engine/
│       │   ├── __init__.py
│       │   ├── game_engine.py        # Core game logic
│       │   ├── resolution.py         # Matrix resolution
│       │   ├── variance.py           # Variance calculations
│       │   └── endings.py            # End condition checks
│       ├── generation/
│       │   ├── __init__.py
│       │   ├── scenario_generator.py # LLM scenario generation
│       │   ├── validator.py          # LLM validation
│       │   └── schemas.py            # JSON schemas
│       ├── opponents/
│       │   ├── __init__.py
│       │   ├── base.py               # Base opponent interface
│       │   ├── deterministic.py      # Rule-based opponents
│       │   ├── historical.py         # LLM historical personas
│       │   └── personas/
│       │       └── __init__.py       # Persona definitions
│       ├── testing/
│       │   ├── __init__.py
│       │   ├── playtester.py         # Automated playtesting
│       │   └── human_simulator.py    # Simulated human players
│       ├── coaching/
│       │   ├── __init__.py
│       │   └── post_game.py          # Post-game analysis
│       └── cli/
│           ├── __init__.py
│           └── app.py                # Textual CLI application
├── scenarios/
│   └── .gitkeep                      # Generated scenario JSON files
├── tests/
│   └── ...
└── scripts/
    ├── generate_scenario.py
    ├── validate_scenario.py
    ├── run_playtest.py
    └── analyze_mechanics.py
```

---

## Phase 1: Core Models and Data Structures

### Milestone 1.1: State Models

**Deliverable**: `src/brinksmanship/models/state.py`

**Implementation Tasks**:
1. Define `GameState` dataclass with all state variables
2. Define `PlayerState` dataclass for per-player state
3. Define `ActionType` enum (COOPERATIVE, COMPETITIVE)
4. Define `ActionResult` dataclass for turn outcomes
5. Implement state validation methods
6. Implement state serialization/deserialization to JSON

**Acceptance Criteria**:
- [ ] `GameState` contains: position_a, position_b, resources_a, resources_b, cooperation_score, stability, risk_level, turn, previous_type_a, previous_type_b
- [ ] All numeric fields are clamped to valid ranges on assignment
- [ ] State can be serialized to JSON and deserialized without loss
- [ ] State includes computed properties for variance calculation
- [ ] Unit tests pass for all state transitions

### Milestone 1.2: Matrix Definitions (Constructor Pattern)

**Deliverable**: `src/brinksmanship/models/matrices.py`

**Design Principle**: Scenarios specify game type + parameters only. Constructors guarantee valid matrices by enforcing ordinal constraints. Nash equilibria are guaranteed by the constraints themselves—no runtime computation needed.

**Implementation Tasks**:
1. Define `MatrixType` enum for all 24 game types
2. Define `MatrixParameters` dataclass with `__post_init__` validation
3. Define `StateDeltas` dataclass for position/resource/risk changes
4. Define `PayoffMatrix` dataclass (output of constructors, never serialized)
5. Implement `MatrixConstructor` protocol with `build(params) -> PayoffMatrix`
6. Implement concrete constructor for each game type enforcing its ordinal constraints
7. Define `CONSTRUCTORS: dict[MatrixType, MatrixConstructor]` registry

**Ordinal Constraints (Verified)** — these guarantee Nash equilibrium structure:

| Game Type | Constraint | Guaranteed Nash Equilibrium |
|-----------|------------|----------------------------|
| Prisoner's Dilemma | T > R > P > S | Unique: (D,D) |
| Deadlock | T > P > R > S | Unique: (D,D), Pareto optimal |
| Harmony | R > T > S > P | Unique: (C,C) |
| Chicken | T > R > S > P | Two pure: (C,D), (D,C) + mixed |
| Stag Hunt | R > T > P > S | Two pure: (C,C) payoff-dom, (D,D) risk-dom |
| Battle of Sexes | Coord > Miscoord, opposite prefs | Two pure + mixed |
| Pure Coordination | Match > Mismatch | Two pure: (A,A), (B,B) |
| Matching Pennies | Zero-sum, symmetric | Unique mixed: (0.5, 0.5) |

**Key Insight**: For 2×2 games, ordinal structure determines equilibrium structure. If the constructor enforces the constraint, the equilibrium is guaranteed by construction.

**MatrixParameters Validation**:
- `scale > 0`
- `position_weight + resource_weight + risk_weight == 1.0`
- All weights non-negative
- Game-type-specific constraints (e.g., `defection_temptation > cooperation_bonus` for PD-family)

**Acceptance Criteria**:
- [ ] `MatrixParameters.__post_init__` rejects invalid parameter combinations
- [ ] Each constructor enforces ordinal constraints (cannot produce invalid matrix)
- [ ] `PayoffMatrix` is never serialized; only `(MatrixType, MatrixParameters)` pairs persist
- [ ] Unit tests: random valid parameters always produce correct ordinal structure
- [ ] Unit tests: verify Nash equilibria match expected (computed once at test time)
- [ ] No runtime Nash equilibrium computation exists in codebase

### Milestone 1.3: Action Definitions

**Deliverable**: `src/brinksmanship/models/actions.py`

**Implementation Tasks**:
1. Define `Action` dataclass with name, type, resource_cost, description
2. Define action menus for each Risk Level tier (1-3, 4-6, 7-9)
3. Implement action classification (Cooperative vs Competitive)
4. Implement action-to-matrix-choice mapping
5. Define special actions (Settlement, Reconnaissance)

**Acceptance Criteria**:
- [ ] Actions are correctly classified as COOPERATIVE or COMPETITIVE
- [ ] Action menus vary by Risk Level as specified in GAME_MANUAL.md
- [ ] Resource costs are enforced (cannot take action if insufficient resources)
- [ ] Settlement action has special handling (bypasses matrix resolution)
- [ ] Unit tests verify action classification

---

## Phase 2: Game Engine

### Milestone 2.1: Core Engine

**Deliverable**: `src/brinksmanship/engine/game_engine.py`

**Implementation Tasks**:
1. Implement `GameEngine` class with scenario loading
2. Implement turn sequencing (8-phase turn structure)
3. Implement simultaneous action collection
4. Implement state update logic (Cooperation Score, Stability)
5. Implement turn history tracking
6. Implement noisy intelligence generation

**Acceptance Criteria**:
- [ ] Engine loads scenario from JSON file
- [ ] Turn sequence follows exact 8-phase structure from GAME_MANUAL.md
- [ ] Cooperation Score updates correctly: CC→+1, DD→-1, mixed→0
- [ ] Stability updates correctly based on switch count
- [ ] Intelligence noise is ±2 uniform for opponent Position and Resources
- [ ] Complete turn history is available for coaching

### Milestone 2.2: Resolution System

**Deliverable**: `src/brinksmanship/engine/resolution.py`

**Implementation Tasks**:
1. Implement matrix resolution for simultaneous actions
2. Implement action-to-matrix-choice mapping
3. Implement payoff application to state
4. Implement settlement negotiation logic
5. Implement reconnaissance game (information as game)

**Acceptance Criteria**:
- [ ] Matrix resolution uses hidden payoff values from scenario
- [ ] Payoffs are scaled by Act Multiplier (0.5×, 1.0×, 1.5×)
- [ ] Settlement constraints are enforced (VP ranges based on Position)
- [ ] Reconnaissance resolves as Matching Pennies variant
- [ ] Resolution returns complete `ActionResult` with all changes

### Milestone 2.3: Variance and Final Resolution

**Deliverable**: `src/brinksmanship/engine/variance.py`

**Implementation Tasks**:
1. Implement variance calculation formula exactly as specified
2. Implement Final Resolution VP calculation
3. Implement symmetric noise application
4. Implement VP clamping to [5, 95]

**Acceptance Criteria**:
- [ ] `Shared_σ = Base_σ × Chaos_Factor × Instability_Factor × Act_Multiplier`
- [ ] All factors calculated correctly from state
- [ ] Single random draw affects both players symmetrically
- [ ] VP sum to 100 exactly
- [ ] Unit tests verify variance ranges for known scenarios

### Milestone 2.4: Ending Conditions

**Deliverable**: `src/brinksmanship/engine/endings.py`

**Implementation Tasks**:
1. Implement deterministic ending checks (Risk=10, Position=0, Resources=0)
2. Implement Crisis Termination probability check
3. Implement natural ending check (turn >= max_turn)
4. Implement ending type enum and result packaging

**Acceptance Criteria**:
- [ ] Risk=10 triggers Mutual Destruction (both get 20 VP)
- [ ] Position=0 triggers loss (10 VP) for that player
- [ ] Resources=0 triggers loss (15 VP) for that player
- [ ] Crisis Termination probability = (Risk - 6) × 0.10 for Risk > 6
- [ ] Crisis Termination only checked for Turn >= 9
- [ ] Max turn is hidden from players (10-18 range)

---

## Phase 3: Scenario Generation

### Milestone 3.1: JSON Schema Definition (Constructor Pattern)

**Deliverable**: `src/brinksmanship/generation/schemas.py`

**Design Principle**: Scenarios specify `matrix_type` + `matrix_parameters` only. Raw payoffs are never stored. Matrices are constructed at load time, guaranteeing type correctness.

**Implementation Tasks**:
1. Define JSON schema for complete scenario
2. Define schema for turn definitions with `matrix_type` and `matrix_parameters`
3. Define schema for `MatrixParameters` with valid ranges
4. Define schema for narrative templates
5. Define schema for branch conditions
6. Implement Pydantic models that construct matrices on load

**Scenario JSON Structure**:
```json
{
  "scenario_id": "string",
  "title": "string",
  "setting": "string",
  "max_turns": 10-18,
  "turns": [
    {
      "turn": 1,
      "act": 1,
      "narrative_briefing": "string",
      "matrix_type": "PRISONERS_DILEMMA",
      "matrix_parameters": {
        "scale": 1.0,
        "position_weight": 0.6,
        "resource_weight": 0.2,
        "risk_weight": 0.2,
        "cooperation_bonus": 1.0,
        "defection_temptation": 1.5,
        "punishment_severity": 0.5,
        "sucker_penalty": 2.0
      },
      "action_menu": ["action1", "action2"],
      "outcome_narratives": {
        "CC": "string",
        "CD": "string",
        "DC": "string",
        "DD": "string"
      },
      "branches": {
        "CC": "turn_2a",
        "default": "turn_2b"
      }
    }
  ],
  "branches": {
    "turn_2a": { ... },
    "turn_2b": { ... }
  }
}
```

**What is NOT in the schema**:
- ~~`matrix_payoffs`~~ — raw payoffs are never stored
- ~~State deltas~~ — computed from constructor at load time

**Load-Time Behavior**:
When a scenario is loaded, for each turn:
1. Parse `matrix_type` and `matrix_parameters`
2. Validate parameters via `MatrixParameters.__post_init__`
3. Call `CONSTRUCTORS[matrix_type].build(params)` to get `PayoffMatrix`
4. Store constructed matrix in memory (not persisted)

If any parameter validation or construction fails, the scenario load fails with a clear error.

**Acceptance Criteria**:
- [ ] Schema has no field for raw payoffs
- [ ] Schema enforces `matrix_parameters` ranges via Pydantic validators
- [ ] Schema supports branching structure
- [ ] Loading a scenario automatically constructs matrices
- [ ] Invalid parameter combinations fail at load time with clear errors
- [ ] Scenario round-trips: save → load → save produces identical JSON

### Milestone 3.2: Scenario Generator (Constructor Pattern)

**Deliverable**: `src/brinksmanship/generation/scenario_generator.py`

**Sampling Process** (guarantees valid matrices by construction):
1. **Sample game type**: LLM selects appropriate game type for narrative context
2. **Sample parameters**: LLM suggests parameters within valid ranges for that type
3. **Construct matrix**: Engine calls constructor (deterministic, type-safe)

The LLM never specifies raw payoffs—only types and parameters.

**Implementation Tasks**:
1. Implement `ScenarioGenerator` class using Claude Agent SDK
2. Load generation prompts from `prompts.py`
3. Implement game type sampling (LLM chooses based on narrative/act)
4. Implement parameter sampling (LLM suggests within valid ranges)
5. Validate parameters before storing in scenario JSON
6. Implement act-based parameter scaling (higher stakes in Act III)

**Generation Flow**:
```
For each turn:
  1. LLM generates narrative_briefing
  2. LLM selects matrix_type from available types for this act
  3. LLM suggests matrix_parameters (constrained to valid ranges)
  4. Validate: MatrixParameters.__post_init__ passes
  5. Validate: Constructor can build matrix (call build() to verify)
  6. Store (matrix_type, matrix_parameters) in scenario JSON
```

**Act-Based Constraints**:
- Act I (turns 1-4): Lower `scale`, coordination/trust games preferred
- Act II (turns 5-8): Standard `scale`, confrontation games (Chicken, PD)
- Act III (turns 9+): Higher `scale`, high-stakes games (War of Attrition, Ultimatum)

**Acceptance Criteria**:
- [ ] Generator uses `claude-agent-sdk` for LLM calls
- [ ] LLM never outputs raw payoffs, only types and parameters
- [ ] All generated parameters pass validation before storage
- [ ] Generated scenarios use 8+ distinct matrix types
- [ ] Generated scenarios have 10-18 turn maximum (randomized)
- [ ] Three-act structure reflected in game type and parameter choices
- [ ] Generated scenarios load successfully (matrices construct without error)

### Milestone 3.3: Scenario Validator (Simplified)

**Deliverable**: `src/brinksmanship/generation/validator.py`

**Design Principle**: Matrix correctness is guaranteed by construction. The validator focuses on scenario-level quality, not structural correctness.

**What is NO LONGER validated** (guaranteed by constructors):
- ~~Payoffs match game type~~ — impossible to fail
- ~~Nash equilibria exist~~ — guaranteed by ordinal constraints
- ~~Ordinal constraints hold~~ — enforced by constructor
- ~~Payoff symmetry for symmetric games~~ — constructor responsibility

**What IS validated**:
1. **Game type variety**: ≥8 distinct types across scenario
2. **Act structure compliance**: Turns map to correct acts
3. **Narrative consistency**: LLM check for thematic coherence
4. **Balance analysis**: LLM check for dominant meta-strategies

**Implementation Tasks**:
1. Implement `ScenarioValidator` class
2. Implement game type distribution check (deterministic, fast)
3. Implement act structure check (deterministic, fast)
4. Implement LLM-based narrative consistency check
5. Implement LLM-based balance analysis
6. Generate validation report

**Acceptance Criteria**:
- [ ] Validator does NOT recheck matrix structure (no such code exists)
- [ ] Validator does NOT compute Nash equilibria
- [ ] Game type variety check: ≥8 distinct types required
- [ ] Act structure check: turns 1-4 → Act I, 5-8 → Act II, 9+ → Act III
- [ ] LLM checks focus on narrative and balance only
- [ ] Validation is fast for structural checks (< 100ms)
- [ ] Validation report clearly separates structural vs semantic issues

---

## Phase 4: Opponent System

### Milestone 4.1: Base Opponent Interface

**Deliverable**: `src/brinksmanship/opponents/base.py`

**Implementation Tasks**:
1. Define `Opponent` abstract base class
2. Define `choose_action` method signature
3. Define `receive_result` method for learning
4. Define `get_settlement_response` method
5. Implement opponent factory function

**Acceptance Criteria**:
- [ ] All opponents implement the same interface
- [ ] Interface supports both human and AI opponents
- [ ] Interface includes method for receiving turn results (for learning)
- [ ] Factory function creates opponent by type name

### Milestone 4.2: Deterministic Opponents

**Deliverable**: `src/brinksmanship/opponents/deterministic.py`

**Implementation Tasks**:
1. Implement `NashCalculator` opponent (plays Nash equilibrium)
2. Implement `SecuritySeeker` opponent (Spiral model actor)
3. Implement `Opportunist` opponent (Deterrence model actor)
4. Implement `Erratic` opponent (randomized behavior)
5. Implement `TitForTat` opponent (Axelrod's strategy)
6. Implement `GrimTrigger` opponent (defect forever after betrayal)

**Opponent Type Specifications**:

| Type | Description | Behavioral Pattern |
|------|-------------|-------------------|
| NashCalculator | Pure game theorist | Plays Nash equilibrium, exploits suboptimal play |
| SecuritySeeker | Spiral model actor | Escalates only when threatened, responds to reassurance |
| Opportunist | Deterrence model actor | Probes for weakness, respects demonstrated strength |
| Erratic | Unpredictable | Mixes strategies with noise, can be spooked |
| TitForTat | Reciprocator | Starts cooperative, mirrors opponent's last move |
| GrimTrigger | Punisher | Cooperates until betrayed, then defects forever |

**Acceptance Criteria**:
- [ ] Each opponent type follows documented behavioral pattern
- [ ] Opponents use only observable game state (no cheating)
- [ ] Opponents correctly handle settlement proposals
- [ ] Unit tests verify expected behavior patterns

### Milestone 4.3: Historical Personas

**Deliverable**: `src/brinksmanship/opponents/historical.py` and `src/brinksmanship/opponents/personas/`

**Implementation Tasks**:
1. Implement `HistoricalPersona` class using Claude Agent SDK
2. Define persona prompt templates in `prompts.py`
3. Implement persona library with the following figures:

**Political/Military Personas**:
- **Otto von Bismarck**: Realpolitik, flexible alliances, never fights unwinnable wars
- **Nikita Khrushchev**: Probes for weakness, bold gestures, backs down if opponent holds firm
- **Cardinal Richelieu**: Raison d'état, long game, weakens rivals through proxies
- **Metternich**: Concert of Europe, stability over hegemony, endless negotiation
- **Thucydides' Athenians**: "The strong do what they can, the weak suffer what they must"
- **Machiavelli's Prince**: Fox and lion, strike decisively, maintain appearance of trustworthiness

**Corporate Personas**:
- **Jack Welch**: "Neutron Jack" - aggressive, results-oriented, "rank and yank" mentality, constructive conflict, "be #1 or #2 or get out", speed and simplicity
- **Michael Milken**: Information asymmetry exploitation, high-risk/high-reward, network effects, aggressive deal-making, finds value where others see only risk
- **Warren Buffett**: Long-term value, patience, reputation for fairness, reluctant to engage in hostile actions, strong when position is strong
- **Carl Icahn**: Corporate raider, aggressive pressure, exploits weakness, forces action through confrontation
- **Jamie Dimon**: Calculated risk, fortress balance sheet, opportunistic in crisis

4. Implement persona prompt that includes:
   - Historical context and worldview
   - Characteristic decision-making patterns
   - Known strategic preferences
   - Current game state
   - Action options

5. Implement `generate_new_persona` function for creating new historical figures from description

**Acceptance Criteria**:
- [ ] Each persona has documented historical basis
- [ ] Persona prompts are in `prompts.py`
- [ ] LLM responses are parsed to valid actions
- [ ] Personas maintain consistent behavior within a game
- [ ] New personas can be generated from description + research
- [ ] Unit tests verify personas make reasonable choices

### Milestone 4.4: Persona Research Prompt

**Deliverable**: Addition to `prompts.py`

**Implementation Tasks**:
1. Create prompt for researching historical/corporate figures
2. Prompt should extract: worldview, strategic patterns, negotiation style, risk tolerance
3. Prompt should generate persona definition suitable for gameplay

**Acceptance Criteria**:
- [ ] Research prompt produces usable persona definitions
- [ ] Generated personas are grounded in documented behavior
- [ ] Personas include appropriate risk tolerance characterization

---

## Phase 5: Playtesting Framework

### Milestone 5.1: Human Simulator

**Deliverable**: `src/brinksmanship/testing/human_simulator.py`

**Implementation Tasks**:
1. Implement `HumanSimulator` class using Claude Agent SDK
2. Create prompt for generating diverse human player personas
3. Implement persona generation: risk tolerance, strategic sophistication, emotional state
4. Implement action selection based on simulated human reasoning
5. Implement "realistic mistakes" modeling

**Human Persona Attributes**:
- Risk tolerance (risk-averse, neutral, risk-seeking)
- Strategic sophistication (novice, intermediate, expert)
- Emotional state (calm, stressed, desperate)
- Personality (cooperative, competitive, erratic)

**Acceptance Criteria**:
- [ ] Simulated humans make varied, realistic decisions
- [ ] Different personas exhibit different play patterns
- [ ] Simulated humans occasionally make suboptimal choices (realistic)
- [ ] Personas are generated fresh for each playtest session

### Milestone 5.2: Playtester Framework

**Deliverable**: `src/brinksmanship/testing/playtester.py`

**Implementation Tasks**:
1. Implement `PlaytestRunner` class
2. Implement batch playtest execution
3. Implement result aggregation and statistics
4. Implement game log export
5. Create playtest report generation

**Acceptance Criteria**:
- [ ] Can run N games with specified opponent pairings
- [ ] Aggregates statistics: win rates, average VP, turn counts, ending types
- [ ] Exports complete game logs for analysis
- [ ] Generates summary report with key findings

### Milestone 5.3: Mechanics Analysis Prompt

**Deliverable**: Addition to `prompts.py` and `scripts/analyze_mechanics.py`

**Implementation Tasks**:
1. Create prompt for Claude Code to analyze playtest results
2. Prompt should identify potential issues:
   - Dominant strategies
   - Unbalanced scenarios
   - Unexpected equilibria
   - Variance calibration problems
3. Output actionable recommendations

**Acceptance Criteria**:
- [ ] Analysis prompt reads GAME_MANUAL.md for reference
- [ ] Analysis identifies deviations from intended mechanics
- [ ] Recommendations are specific and actionable
- [ ] Analysis can be run after each batch of playtests

---

## Phase 6: Post-Game Coaching

### Milestone 6.1: Coaching System

**Deliverable**: `src/brinksmanship/coaching/post_game.py`

**Implementation Tasks**:
1. Implement `PostGameCoach` class using Claude Agent SDK
2. Create coaching prompt template in `prompts.py`
3. Implement turn-by-turn analysis
4. Implement Bayesian opponent-type inference reconstruction
5. Implement identification of key decision points
6. Generate narrative coaching report

**Coaching Report Contents**:
- Game summary (turns, ending type, final VP)
- Turn-by-turn analysis with matrix type identification
- Opponent behavior pattern analysis
- Identification of optimal vs. actual choices
- Bayesian type inference trace (what the player should have inferred)
- Key lessons and recommendations

**Acceptance Criteria**:
- [ ] Coaching uses complete game history
- [ ] Analysis correctly identifies matrix types used
- [ ] Bayesian inference walkthrough is mathematically correct
- [ ] Recommendations are specific and educational
- [ ] Report references relevant theory (Schelling, Jervis, etc.)

---

## Phase 7: CLI Interface

### Milestone 7.1: Textual Application

**Deliverable**: `src/brinksmanship/cli/app.py`

**Implementation Tasks**:
1. Implement main menu (New Game, Load Scenario, Settings, Quit)
2. Implement opponent selection screen
3. Implement game screen with:
   - State display panel
   - Narrative panel
   - Action selection panel
   - History panel
4. Implement settlement negotiation UI
5. Implement end-game results screen
6. Implement coaching display

**UI Layout**:
```
┌─────────────────────────────────────────────────────────────────┐
│ Turn 5 | Risk: 4 | Coop: 7 | Stability: 8 | Act II              │
├─────────────────────────────────────────────────────────────────┤
│ BRIEFING                                                        │
│ ─────────────────────────────────────────────────────────────── │
│ The council has convened. Your opponent's delegates arrive      │
│ with unexpected proposals...                                     │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│ YOUR STATUS           │ INTELLIGENCE                            │
│ Position: 6           │ Opponent Position: ~5-7                 │
│ Resources: 4          │ Opponent Resources: ~3-5                │
├─────────────────────────────────────────────────────────────────┤
│ ACTIONS                                                         │
│ [1] Hold Position (Cooperative)                                 │
│ [2] Escalate Pressure (Competitive) - 1 Resource                │
│ [3] Propose Settlement                                          │
│ [4] Back Channel (Cooperative) - 1 Resource                     │
│ [5] Show of Force (Competitive) - 2 Resources                   │
├─────────────────────────────────────────────────────────────────┤
│ HISTORY: T1:CC→+1 | T2:CD→-1 | T3:CC→+1 | T4:CC→+1              │
└─────────────────────────────────────────────────────────────────┘
```

**Acceptance Criteria**:
- [ ] Application launches and displays main menu
- [ ] All game state is clearly displayed
- [ ] Actions show type classification and resource cost
- [ ] Noisy intelligence is displayed (not exact values)
- [ ] Settlement negotiation has clear UI
- [ ] End-game shows results and offers coaching
- [ ] Application handles all ending conditions gracefully

---

## Phase 8: Integration and Scripts

### Milestone 8.1: Entry Point Scripts

**Deliverables**: `scripts/` directory

**Scripts to Implement**:

1. `generate_scenario.py`:
   - CLI arguments: theme, output path
   - Generates and validates scenario
   - Saves to scenarios/ directory

2. `validate_scenario.py`:
   - CLI arguments: scenario path
   - Runs validation LLM
   - Outputs validation report

3. `run_playtest.py`:
   - CLI arguments: scenario, num_games, opponent_types
   - Runs batch playtests
   - Outputs statistics and logs

4. `analyze_mechanics.py`:
   - CLI arguments: playtest_log_directory
   - Runs analysis LLM
   - Outputs recommendations

**Acceptance Criteria**:
- [ ] All scripts have --help documentation
- [ ] Scripts handle errors gracefully
- [ ] Scripts log progress for long-running operations
- [ ] Output formats are consistent and parseable

### Milestone 8.2: Prompts Module

**Deliverable**: Complete `src/brinksmanship/prompts.py`

All prompts consolidated in one file for easy modification:

```python
# prompts.py structure

# Scenario Generation
SCENARIO_GENERATION_SYSTEM_PROMPT = """..."""
SCENARIO_GENERATION_USER_PROMPT_TEMPLATE = """..."""

# Scenario Validation
SCENARIO_VALIDATION_SYSTEM_PROMPT = """..."""
SCENARIO_VALIDATION_USER_PROMPT_TEMPLATE = """..."""

# Historical Personas
HISTORICAL_PERSONA_SYSTEM_PROMPT = """..."""
PERSONA_BISMARCK = """..."""
PERSONA_KHRUSHCHEV = """..."""
PERSONA_RICHELIEU = """..."""
PERSONA_METTERNICH = """..."""
PERSONA_ATHENIANS = """..."""
PERSONA_PRINCE = """..."""
PERSONA_WELCH = """..."""
PERSONA_MILKEN = """..."""
PERSONA_BUFFETT = """..."""
PERSONA_ICAHN = """..."""
PERSONA_DIMON = """..."""

# Persona Research
PERSONA_RESEARCH_PROMPT = """..."""

# Human Simulation
HUMAN_SIMULATOR_SYSTEM_PROMPT = """..."""
HUMAN_PERSONA_GENERATION_PROMPT = """..."""

# Post-Game Coaching
COACHING_SYSTEM_PROMPT = """..."""
COACHING_ANALYSIS_PROMPT_TEMPLATE = """..."""

# Mechanics Analysis
MECHANICS_ANALYSIS_SYSTEM_PROMPT = """..."""
MECHANICS_ANALYSIS_PROMPT_TEMPLATE = """..."""
```

**Acceptance Criteria**:
- [ ] All prompts are in prompts.py
- [ ] No hardcoded prompts elsewhere in codebase
- [ ] Prompts have clear documentation comments
- [ ] Template variables use consistent naming

---

## Phase 9: Playtesting and Iteration

### Milestone 9.1: Claude Code Playtest Prompt

**Deliverable**: Prompt for Claude Code to run playtesting and identify issues

```markdown
# Playtest Analysis Task

You are tasked with playtesting Brinksmanship and identifying potential issues in game mechanics.

## Setup

1. Read the game manual: `GAME_MANUAL.md`
2. Review the prompts: `src/brinksmanship/prompts.py`
3. Examine the engine implementation: `src/brinksmanship/engine/`

## Playtest Procedure

1. Generate 3 scenarios with different themes (Cold War, Corporate, Ancient)
2. For each scenario, run 10 games with these pairings:
   - NashCalculator vs NashCalculator
   - TitForTat vs Opportunist
   - SecuritySeeker vs Opportunist
   - Human (simulated) vs each deterministic type
   - Historical persona vs Historical persona

3. Collect statistics:
   - Win rates by opponent type
   - Average turn count
   - Ending type distribution
   - Settlement rate
   - Average variance at game end

## Analysis Questions

Answer each question with evidence from playtests:

1. **Dominant Strategies**: Is there any strategy that wins regardless of opponent? If so, describe it and propose a fix.

2. **Variance Calibration**: Are final VP spreads appropriate? Too narrow (game feels deterministic)? Too wide (feels random)?

3. **Settlement Incentives**: Do players settle when they should? Is settlement ever strictly dominated?

4. **Stability Mechanism**: Does the consistency reward work as intended? Can players exploit it?

5. **Crisis Termination**: Does the uncertain ending prevent backward induction in practice?

6. **Opponent Type Distinguishability**: Can a player reasonably infer opponent type from behavior?

7. **Scenario Balance**: Do all generated scenarios give both players viable paths to victory?

8. **Historical Personas**: Do corporate personas (Welch, Milken, etc.) behave consistently with their documented patterns?

## Output Format

Produce a report with:
1. Executive Summary (major findings)
2. Statistical Tables
3. Issue List (with severity: Critical/Major/Minor)
4. Recommended Changes (specific, actionable)
5. Successful Mechanics (what's working well)
```

**Acceptance Criteria**:
- [ ] Prompt is comprehensive and specific
- [ ] Output format enables actionable iteration
- [ ] Analysis covers all core mechanics
- [ ] Findings can be tracked as issues

---

## SDK Reference

### Claude Agent SDK Usage

**Installation**:
```bash
pip install claude-agent-sdk
```

**Basic Query**:
```python
import asyncio
from claude_agent_sdk import query, ClaudeAgentOptions

async def generate_scenario(theme: str) -> dict:
    options = ClaudeAgentOptions(
        system_prompt=SCENARIO_GENERATION_SYSTEM_PROMPT
    )
    
    response_text = ""
    async for message in query(
        prompt=SCENARIO_GENERATION_USER_PROMPT_TEMPLATE.format(theme=theme),
        options=options
    ):
        if hasattr(message, 'content'):
            for block in message.content:
                if hasattr(block, 'text'):
                    response_text += block.text
    
    return parse_scenario_json(response_text)
```

**Interactive Client**:
```python
from claude_agent_sdk import ClaudeSDKClient

async def run_historical_opponent(persona_prompt: str, game_state: dict) -> str:
    client = ClaudeSDKClient()
    
    async for message in client.query(
        prompt=format_action_request(persona_prompt, game_state)
    ):
        if hasattr(message, 'content'):
            return extract_action(message.content)
```

### Standard Anthropic SDK (Alternative)

For simpler LLM calls without agent features:

```python
from anthropic import Anthropic

client = Anthropic()

def generate_scenario(theme: str) -> dict:
    message = client.messages.create(
        model="claude-sonnet-4-5-20250929",
        max_tokens=8000,
        system=SCENARIO_GENERATION_SYSTEM_PROMPT,
        messages=[
            {"role": "user", "content": SCENARIO_GENERATION_USER_PROMPT_TEMPLATE.format(theme=theme)}
        ]
    )
    return parse_scenario_json(message.content[0].text)
```

---

## Testing Strategy

### Unit Tests (Constructor Correctness)

These tests prove constructors are correct once; no runtime verification needed thereafter.

**Matrix Constructor Tests**:
- For each game type, sample 100 random valid parameters
- Verify constructed matrix satisfies ordinal constraints
- Verify Nash equilibrium structure matches expected (computed once at test time)

**Parameter Validation Tests**:
- `MatrixParameters.__post_init__` rejects invalid combinations
- Each constructor's type-specific validation rejects incompatible params
- Edge cases: scale=0, negative weights, weights not summing to 1

**State Model Tests**:
- State serialization/deserialization round-trips
- Field clamping to valid ranges
- Computed variance properties

### Unit Tests (Engine)

- Variance formula correctness
- Ending condition triggers
- Action classification
- Cooperation/Stability update rules

### Integration Tests

- Scenario loading constructs all matrices without error
- Full turn sequence execution with constructed matrices
- Opponent decision-making
- Settlement negotiation flow

### Validation Taxonomy

| What | When Verified | How |
|------|---------------|-----|
| Ordinal constraints | Test time (once) | Unit tests prove constructors correct |
| Nash equilibrium structure | Test time (once) | Unit tests verify expected equilibria |
| Parameter ranges | Load time | `MatrixParameters.__post_init__` |
| Game type variety | Generation/Validation | Count distinct types |
| Narrative consistency | Generation/Validation | LLM check |

### Playtest Analysis

- Statistical validation of mechanics
- Balance verification
- Dominant strategy detection

---

## Dependencies

```toml
[project]
name = "brinksmanship"
version = "0.1.0"
dependencies = [
    "claude-agent-sdk>=0.1.0",
    "anthropic>=0.30.0",
    "textual>=0.50.0",
    "pydantic>=2.0.0",
    "numpy>=1.24.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0.0",
    "pytest-asyncio>=0.21.0",
    "mypy>=1.0.0",
    "ruff>=0.1.0",
]
```

---

## Implementation Order

**Week 1**: Phase 1 (Models) + Phase 2.1-2.2 (Core Engine)
**Week 2**: Phase 2.3-2.4 (Variance, Endings) + Phase 3 (Scenario Generation)
**Week 3**: Phase 4 (Opponents)
**Week 4**: Phase 5 (Playtesting) + Phase 6 (Coaching)
**Week 5**: Phase 7 (CLI) + Phase 8 (Integration)
**Week 6**: Phase 9 (Playtesting and Iteration)

---

## Success Metrics

1. **Mechanical Correctness**: All formulas match GAME_MANUAL.md exactly
2. **No Dominant Strategy**: Statistical analysis shows no strategy wins >60% against all opponents
3. **Settlement Rate**: 40-60% of games end in settlement (healthy negotiation incentive)
4. **Variance Calibration**: Final VP standard deviation of 15-25 in typical games
5. **Player Experience**: Human playtesters report engaging, non-obvious decisions
6. **Opponent Variety**: Each opponent type has distinct, recognizable play patterns
7. **Scenario Variety**: Generated scenarios feel distinct and thematically appropriate

---

*Document Version: 1.0*
*Last Updated: January 2026*
