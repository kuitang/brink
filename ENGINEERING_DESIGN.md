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
│       ├── cli/
│       │   ├── __init__.py
│       │   └── app.py                # Textual CLI application
│       └── storage/
│           ├── __init__.py
│           ├── repository.py         # Abstract repository interface
│           ├── file_repo.py          # JSON file implementation
│           └── sqlite_repo.py        # SQLite implementation
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
| Volunteer's Dilemma | F > W > D (free-ride > work > disaster) | Two pure + mixed |
| Leader | G > H > B > C (lead success > follow > stuck > clash) | Two pure (one leads) |
| Inspection Game | L > c, g > p (loss > cost, gain > penalty) | Unique mixed |
| Reconnaissance | Zero-sum information game | Unique mixed: (0.5, 0.5) |
| Security Dilemma | T > R > P > S (same as PD) | Unique: (D,D) |

**Total Viable 2×2 Games**: 13

**Collapsed Sequential Games** (represented as 2×2 strategy space):
- Trust Game → PD variant with dominant row
- Ultimatum Game → Chicken variant
- Entry Deterrence → Unique Nash (Enter, Accommodate)
- Dollar Auction → Commit/Fold 2×2
- War of Attrition → Continue/Quit 2×2

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

### Milestone 1.4: Storage Repository

**Deliverables**: `src/brinksmanship/storage/`

**Design Principle**: Abstract storage behind a repository interface. Both file-based (JSON) and SQLite backends implement the same interface. The webapp and CLI use the repository—they don't know which backend is active.

**Implementation Tasks**:
1. Define `ScenarioRepository` abstract base class
2. Implement `FileScenarioRepository` (JSON files in `scenarios/` directory)
3. Implement `SQLiteScenarioRepository` (SQLAlchemy-based)
4. Define `GameRecordRepository` abstract base class
5. Implement `FileGameRecordRepository` for game state persistence
6. Implement `SQLiteGameRecordRepository` for database persistence
7. Implement factory function that returns repository based on config

**Repository Interface**:
```python
class ScenarioRepository(ABC):
    @abstractmethod
    def list_scenarios(self) -> list[dict]:
        """Return metadata for all available scenarios.

        Returns list of: {id, name, setting, max_turns}
        """
        pass

    @abstractmethod
    def get_scenario(self, scenario_id: str) -> Optional[dict]:
        """Load complete scenario by ID."""
        pass

    @abstractmethod
    def get_scenario_by_name(self, name: str) -> Optional[dict]:
        """Load scenario by name (case-insensitive search)."""
        pass

    @abstractmethod
    def save_scenario(self, scenario: dict) -> str:
        """Save scenario, return ID.

        Scenario must have 'name' field. For file backend, ID is
        slugified name (e.g., 'Cuban Missile Crisis' -> 'cuban-missile-crisis').
        For SQLite, ID is auto-generated but name is indexed.
        """
        pass

    @abstractmethod
    def delete_scenario(self, scenario_id: str) -> bool:
        """Delete scenario. Returns True if deleted."""
        pass

class GameRecordRepository(ABC):
    @abstractmethod
    def save_game(self, game_id: str, state: dict) -> None:
        """Persist complete game state."""
        pass

    @abstractmethod
    def load_game(self, game_id: str) -> Optional[dict]:
        """Load game state by ID."""
        pass

    @abstractmethod
    def list_games(self, user_id: Optional[int] = None) -> list[dict]:
        """List games, optionally filtered by user."""
        pass
```

**Configuration**:
```python
# config.py or environment variable
STORAGE_BACKEND = "file"  # or "sqlite"
SCENARIOS_PATH = "scenarios/"
DATABASE_URI = "sqlite:///instance/brinksmanship.db"
```

**Acceptance Criteria**:
- [ ] `ScenarioRepository` interface defined with list/get/save/delete
- [ ] `FileScenarioRepository` reads/writes JSON files
- [ ] `SQLiteScenarioRepository` uses SQLAlchemy models
- [ ] `GameRecordRepository` interface defined
- [ ] Both backends pass identical integration tests
- [ ] Factory function returns correct backend based on config
- [ ] CLI and webapp use repository, not direct file access

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
1. Implement variance calculation formula (revised bounds)
2. Implement Final Resolution VP calculation with symmetric renormalization
3. Implement symmetric noise application (noise applied to both, then renormalized)
4. Implement VP clamping to [5, 95] with renormalization

**Variance Formula** (revised for playable σ range of 10-40):
```python
base_sigma = 8 + (risk_level * 1.2)      # 8-20
chaos_factor = 1.2 - (coop_score / 50)   # 1.0-1.2
instability_factor = 1 + (10 - stability) / 20  # 1.0-1.45
act_multiplier = {1: 0.8, 2: 1.0, 3: 1.2}[act]
shared_sigma = base_sigma * chaos_factor * instability_factor * act_multiplier
```

**Acceptance Criteria**:
- [ ] `Shared_σ` stays in range 10-40 for all valid states
- [ ] Symmetric renormalization: both players clamped, then normalized to sum to 100
- [ ] VP sum to 100 exactly after renormalization
- [ ] Unit tests verify: peaceful ~10σ, neutral ~19σ, tense ~27σ, crisis ~37σ

### Milestone 2.4: Ending Conditions

**Deliverable**: `src/brinksmanship/engine/endings.py`

**Implementation Tasks**:
1. Implement deterministic ending checks (Risk=10, Position=0, Resources=0)
2. Implement Crisis Termination probability check (revised formula)
3. Implement natural ending check (turn >= max_turn)
4. Implement ending type enum and result packaging

**Crisis Termination** (revised for better planning):
```python
# Only checked for Turn >= 10 and Risk > 7
if turn >= 10 and risk_level > 7:
    p_termination = (risk_level - 7) * 0.08
    # Risk 8: 8%, Risk 9: 16%, Risk 10: automatic (100%)
```

**Acceptance Criteria**:
- [ ] Risk=10 triggers Mutual Destruction (both get 20 VP)
- [ ] Position=0 triggers loss (10 VP) for that player
- [ ] Resources=0 triggers loss (15 VP) for that player
- [ ] Crisis Termination probability = (Risk - 7) × 0.08 for Risk > 7
- [ ] Crisis Termination only checked for Turn >= 10
- [ ] Max turn range: 12-16 (narrower, hidden from players)

### Milestone 2.5: State Delta System

**Deliverable**: `src/brinksmanship/engine/state_deltas.py`

**Implementation Tasks**:
1. Define `StateDeltas` dataclass for outcome effects
2. Define `StateDeltaTemplate` for each matrix type with bounds
3. Implement validation that deltas are within bounds and ordinal-consistent
4. Implement act scaling (×0.7, ×1.0, ×1.3)

**State Delta Constraints**:
```python
GLOBAL_BOUNDS = {
    "position": (-1.5, 1.5),     # Per player, per turn
    "resource_cost": (0.0, 1.0), # Per player, per turn
    "risk": (-1.0, 2.0),         # Shared, per turn
}

# Position changes must be near-zero-sum
assert abs(delta_pos_a + delta_pos_b) <= 0.5
```

**Example Template for Prisoner's Dilemma**:
```python
PD_DELTA_TEMPLATE = {
    "CC": {"pos_a": (0.3, 0.7), "pos_b": (0.3, 0.7), "risk": (-1.0, 0.0)},
    "CD": {"pos_a": (-1.2, -0.5), "pos_b": (0.5, 1.2), "risk": (0.0, 1.0)},
    "DC": {"pos_a": (0.5, 1.2), "pos_b": (-1.2, -0.5), "risk": (0.0, 1.0)},
    "DD": {"pos_a": (-0.7, 0.0), "pos_b": (-0.7, 0.0), "risk": (0.5, 1.5)},
}
```

**Acceptance Criteria**:
- [ ] StateDeltas dataclass with pos_a, pos_b, res_cost_a, res_cost_b, risk_delta
- [ ] Templates defined for all 13 viable game types
- [ ] Validation rejects out-of-bounds deltas
- [ ] Validation enforces ordinal consistency (T > R > P > S for PD)
- [ ] Act scaling correctly applied to deltas

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
  "max_turns": 12-16,
  "turns": [
    {
      "turn": 1,
      "act": 1,
      "narrative_briefing": "string",
      "matrix_type": "PRISONERS_DILEMMA",
      "matrix_parameters": {
        "scale": 1.0,
        "cooperation_bonus": 1.0,
        "defection_temptation": 1.5,
        "punishment_severity": 0.5,
        "sucker_penalty": 2.0
      },
      "state_deltas": {
        "CC": {"pos_a": 0.5, "pos_b": 0.5, "risk": -0.5},
        "CD": {"pos_a": -1.0, "pos_b": 1.0, "risk": 0.5},
        "DC": {"pos_a": 1.0, "pos_b": -1.0, "risk": 0.5},
        "DD": {"pos_a": -0.3, "pos_b": -0.3, "risk": 1.0, "res_cost": 0.5}
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

**Game Type Selection Heuristics**:

The generator classifies user prompts by theme, then selects game types appropriate to act and theme:

| Theme | Keywords | Act I Games | Act II Games | Act III Games |
|-------|----------|-------------|--------------|---------------|
| crisis | war, nuclear, confrontation | Inspection, Stag Hunt, PD | Chicken, Security Dilemma | Chicken, Security Dilemma, Deadlock |
| rivals | rival, enemy, competitor | Inspection, Stag Hunt | Chicken, PD, Deadlock | Chicken, Deadlock, Security Dilemma |
| allies | ally, alliance, partner | Harmony, Pure Coordination, Stag Hunt | Battle of Sexes, Stag Hunt, Leader | Volunteers Dilemma, Stag Hunt, Battle of Sexes |
| espionage | spy, intelligence, secret | Inspection, Reconnaissance | Inspection, Matching Pennies, PD | Inspection, Chicken, PD |
| default | (other) | Stag Hunt, Pure Coordination, Leader | PD, Chicken, Battle of Sexes | Chicken, Security Dilemma, PD |

**Variety Constraints**:
- Never repeat same game type twice in row
- High risk (≥7): Favor Chicken (confrontation) or Stag Hunt (de-escalation)
- High cooperation score (≥7): Favor trust-based games (Stag Hunt, Harmony)
- Low cooperation score (≤3): Favor confrontational games (Chicken, Deadlock)

**Act-Based Scaling**:
- Act I (turns 1-4): Delta scaling ×0.7, coordination/trust games preferred
- Act II (turns 5-8): Delta scaling ×1.0, confrontation games (Chicken, PD)
- Act III (turns 9+): Delta scaling ×1.3, high-stakes decisive games

**Acceptance Criteria**:
- [ ] Generator uses `claude-agent-sdk` for LLM calls
- [ ] LLM never outputs raw payoffs, only types and parameters
- [ ] All generated parameters pass validation before storage
- [ ] Generated scenarios use 8+ distinct matrix types
- [ ] Generated scenarios have 10-18 turn maximum (randomized)
- [ ] Three-act structure reflected in game type and parameter choices
- [ ] Generated scenarios load successfully (matrices construct without error)

### Milestone 3.3: Scenario Validator (Agentic with Tool Execution)

**Deliverable**: `src/brinksmanship/generation/validator.py` and `scripts/quick_validate.py`

**Design Principle**: Matrix correctness is guaranteed by construction. The validator focuses on scenario-level quality using **tool execution for deterministic checks** and **game simulations for balance analysis**—NOT LLM reasoning about game theory.

**What is NO LONGER validated** (guaranteed by constructors):
- ~~Payoffs match game type~~ — impossible to fail
- ~~Nash equilibria exist~~ — guaranteed by ordinal constraints
- ~~Ordinal constraints hold~~ — enforced by constructor
- ~~Payoff symmetry for symmetric games~~ — constructor responsibility

**What IS validated**:
1. **Game type variety**: ≥8 distinct types across scenario (deterministic check)
2. **Act structure compliance**: Turns map to correct acts (deterministic check)
3. **Balance analysis**: **Run actual game simulations** to detect dominant strategies
4. **Narrative consistency**: LLM check for thematic coherence (ONLY subjective check)

**Agentic Tool Usage**:
```python
from claude_agent_sdk import query, ClaudeAgentOptions

async def validate_scenario(scenario_path: str):
    options = ClaudeAgentOptions(
        allowed_tools=["Read", "Bash", "Write"],
        system_prompt=SCENARIO_VALIDATION_SYSTEM_PROMPT,
        permission_mode="acceptEdits"
    )

    # Agent executes these tools autonomously:
    # 1. Bash: python scripts/quick_validate.py {scenario_path}
    #    → Returns JSON with structural check results
    # 2. Bash: python scripts/run_playtest.py --quick --games 50 {scenario_path}
    #    → Returns JSON with win rates, turn lengths, ending distributions
    # 3. Read: validation_results.json
    #    → Agent analyzes statistical output
    # 4. LLM reasoning: ONLY for narrative consistency
    # 5. Write: validation_report.md

    async for message in query(
        prompt=f"""Validate scenario at {scenario_path}:
1. Run: python scripts/quick_validate.py {scenario_path}
2. Run: python scripts/run_playtest.py --quick --games 50 --scenario {scenario_path}
3. Analyze simulation results statistically (dominant strategy = >70% win rate)
4. Check narrative consistency (LLM judgment)
5. Write validation report""",
        options=options
    ):
        yield message
```

**Simulation-Based Balance Check**:
```bash
# Agent runs this via Bash tool:
python scripts/run_playtest.py \
    --quick \
    --games 50 \
    --scenario scenarios/test.json \
    --pairings "Nash:Nash,TitForTat:Opportunist,SecuritySeeker:Opportunist" \
    --output validation_results.json

# Dominant strategy detected if ANY pairing shows >70% win rate
# Output is JSON that agent parses—no LLM game theory reasoning
```

**Implementation Tasks**:
1. Implement `ScenarioValidator` class using Claude Agent SDK **with tool access**
2. Implement `scripts/quick_validate.py` (deterministic structural checks)
3. Agent uses **Bash tool** to run Python validation scripts
4. Agent uses **Bash tool** to run game simulations
5. Agent uses **Read tool** to parse simulation output JSON
6. LLM reasoning used ONLY for narrative consistency
7. Agent uses **Write tool** to produce validation report

**Acceptance Criteria**:
- [ ] Validator does NOT use LLM to reason about game theory or balance
- [ ] Balance analysis runs 50+ actual game simulations via Bash tool
- [ ] Dominant strategy detection: statistical threshold (>70% win rate), not LLM judgment
- [ ] Game type variety check: deterministic Python code
- [ ] Act structure check: deterministic Python code
- [ ] LLM checks focus on narrative consistency ONLY
- [ ] Validation is fast for structural checks (< 100ms)
- [ ] Validation report includes statistical tables from simulations

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

### Milestone 4.3: Historical Personas (Agentic with WebSearch)

**Deliverable**: `src/brinksmanship/opponents/historical.py` and `src/brinksmanship/opponents/personas/`

**Design Principle**: Persona definitions are grounded in documented historical behavior. For well-known figures (Bismarck, Khrushchev, etc.), the LLM's training data is sufficient—WebSearch is unnecessary and adds latency. WebSearch is **optional** for user-created personas based on obscure figures.

**Implementation Tasks**:
1. Implement `HistoricalPersona` class using Claude Agent SDK
2. Define persona prompt templates in `prompts.py` (include characteristic quotes)
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

5. Implement `generate_new_persona` function using **WebSearch for research**

**Acceptance Criteria**:
- [ ] Each persona has documented historical basis
- [ ] Persona prompts are in `prompts.py`
- [ ] LLM responses are parsed to valid actions
- [ ] Personas maintain consistent behavior within a game
- [ ] New personas can be generated from description + **WebSearch research**
- [ ] Unit tests verify personas make reasonable choices

### Milestone 4.4: Custom Persona Generator (Optional WebSearch)

**Deliverable**: `src/brinksmanship/opponents/persona_generator.py` and addition to `prompts.py`

**Design Principle**: New personas can be created from a figure name/description. For famous figures, LLM training data suffices. WebSearch is **opt-in** for obscure figures where LLM knowledge may be incomplete or outdated. Default to LLM-only for speed (~5s vs ~30s with search).

**Persona Generation (LLM-only, fast)**:
```python
from brinksmanship.llm import generate_json
from brinksmanship.prompts import PERSONA_GENERATION_PROMPT

async def generate_persona(figure_name: str, use_search: bool = False) -> dict:
    """Generate a persona definition from a figure name.

    Args:
        figure_name: Name of historical/fictional figure
        use_search: If True, use WebSearch for obscure figures (slower)

    Default (use_search=False): ~5 seconds, uses LLM training knowledge
    With search (use_search=True): ~30 seconds, for obscure figures
    """
    if use_search:
        return await _research_persona_with_search(figure_name)

    # Fast path: LLM already knows famous figures
    return await generate_json(
        prompt=PERSONA_GENERATION_PROMPT.format(figure_name=figure_name),
        system_prompt="You are an expert on historical and fictional strategists.",
    )
```

**When to use WebSearch**:
- Famous figures (Bismarck, Khrushchev, Machiavelli): **NO** - LLM knows them
- Obscure historical figures: **YES** - LLM may have incomplete info
- Contemporary business figures: **MAYBE** - for recent actions post-cutoff
- Fictional characters: **NO** - LLM knows them from training

**Example output** (generated from LLM knowledge alone):
```json
{
  "name": "Otto von Bismarck",
  "worldview": "Realpolitik - pursue national interest through pragmatic means",
  "strategic_patterns": [
    "Probes opponent's resolve before committing",
    "Creates situations where opponents appear as aggressors",
    "Maintains multiple alliance options, commits only when advantageous",
    "Avoids fights he cannot win; patient when odds unfavorable"
  ],
  "risk_tolerance": 4,
  "characteristic_quotes": [
    "Politics is the art of the possible",
    "The great questions of the day will not be settled by speeches and majority decisions but by iron and blood"
  ],
  "trigger_conditions": {
    "escalate": "When opponent shows weakness or isolation",
    "de_escalate": "When facing strong coalition or uncertain odds"
  }
}
```

**Implementation Tasks**:
1. Implement `PersonaResearcher` class using `agentic_query` with WebSearch
2. Create `PERSONA_RESEARCH_SYSTEM_PROMPT` in `prompts.py`
3. Implement structured output parsing for persona definitions
4. Cache research results to avoid redundant web searches
5. Implement source citation tracking for transparency

**Acceptance Criteria**:
- [ ] Research agent uses WebSearch and WebFetch tools autonomously
- [ ] Generated personas include source citations
- [ ] Research results are cached (don't re-search same figure)
- [ ] Personas include all required fields: worldview, patterns, risk, triggers, settlement
- [ ] Generated personas are grounded in documented behavior (verifiable sources)
- [ ] Personas include appropriate risk tolerance characterization (1-10 with justification)

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

### Milestone 5.2: Playtester Framework (Agentic with Subagents)

**Deliverable**: `src/brinksmanship/testing/playtester.py` and `scripts/run_playtest.py`

**Design Principle**: The playtester uses **subagents for parallel game execution** and **Bash tool for running Python scripts**. This enables high-throughput testing with deterministic execution.

**Implementation Tasks**:
1. Implement `PlaytestRunner` class with subagent orchestration
2. Implement `scripts/run_playtest.py` for batch execution (pure Python, no LLM)
3. Agent uses **Bash tool** to run playtest batches
4. Agent uses **Task tool** to spawn parallel subagents for different pairings
5. Implement result aggregation from JSON outputs
6. Implement game log export

**Agentic Orchestration Pattern**:
```python
from claude_agent_sdk import query, ClaudeAgentOptions, AgentDefinition

async def run_playtest_suite(scenario_path: str, num_games: int = 100):
    """Run comprehensive playtest suite using subagents.

    Main agent orchestrates, subagents handle specific test categories.
    """
    options = ClaudeAgentOptions(
        allowed_tools=["Bash", "Read", "Write", "Task"],
        agents={
            "deterministic-tester": AgentDefinition(
                description="Tests deterministic opponent pairings",
                prompt="Run games between algorithmic opponents and collect stats.",
                tools=["Bash", "Read"]
            ),
            "persona-tester": AgentDefinition(
                description="Tests historical persona matchups",
                prompt="Run games between historical personas and verify behavior.",
                tools=["Bash", "Read", "WebSearch"]  # May need to verify persona accuracy
            ),
            "human-sim-tester": AgentDefinition(
                description="Tests simulated human play patterns",
                prompt="Run games with simulated humans and check for realistic behavior.",
                tools=["Bash", "Read"]
            ),
        }
    )

    # Main agent spawns subagents in parallel for different test categories
    async for message in query(
        prompt=f"""Run playtest suite for {scenario_path}:

1. Spawn deterministic-tester subagent:
   Bash: python scripts/run_playtest.py --scenario {scenario_path} \
         --pairings "Nash:Nash,TitForTat:Opportunist,SecuritySeeker:GrimTrigger" \
         --games {num_games} --output results/deterministic.json

2. Spawn persona-tester subagent:
   Bash: python scripts/run_playtest.py --scenario {scenario_path} \
         --pairings "Bismarck:Khrushchev,Buffett:Icahn,Welch:Dimon" \
         --games {num_games} --output results/personas.json

3. Spawn human-sim-tester subagent:
   Bash: python scripts/run_playtest.py --scenario {scenario_path} \
         --human-sim --games {num_games} --output results/human_sim.json

4. Aggregate all results and produce summary statistics.
5. Write final report to results/playtest_report.json""",
        options=options
    ):
        yield message
```

**Playtest Script** (`scripts/run_playtest.py`):
```bash
# Pure Python, no LLM - deterministic execution
python scripts/run_playtest.py \
    --scenario scenarios/cold_war.json \
    --pairings "Nash:Nash,TitForTat:Opportunist" \
    --games 100 \
    --output playtest_results.json \
    --log-dir logs/

# Output JSON structure:
# {
#   "pairings": {"Nash:Nash": {"wins_a": 45, "wins_b": 42, "ties": 13, ...}},
#   "aggregate": {"avg_turns": 12.3, "settlement_rate": 0.52, ...},
#   "logs": ["logs/game_001.json", "logs/game_002.json", ...]
# }
```

**Acceptance Criteria**:
- [ ] Agent uses Bash tool to run Python playtest scripts
- [ ] Agent spawns subagents for parallel test categories
- [ ] Pure Python scripts handle game execution (deterministic, fast)
- [ ] Can run N games with specified opponent pairings via CLI
- [ ] Aggregates statistics: win rates, average VP, turn counts, ending types
- [ ] Exports complete game logs for analysis
- [ ] Generates summary report as structured JSON

### Milestone 5.3: Mechanics Analysis Agent (Agentic with Tool Execution)

**Deliverable**: `scripts/analyze_mechanics.py` and addition to `prompts.py`

**Design Principle**: Mechanics analysis combines **deterministic statistical analysis** (Python) with **LLM interpretation** of results. The agent runs analysis scripts, reads outputs, and interprets patterns.

**Agentic Analysis Workflow**:
```python
from brinksmanship.llm import agentic_query

async def analyze_mechanics(playtest_dir: str) -> str:
    """Analyze playtest results for mechanics issues.

    Agent workflow:
    1. Run statistical analysis scripts via Bash
    2. Read GAME_MANUAL.md for intended mechanics
    3. Compare actual vs intended behavior
    4. Identify issues and recommend fixes
    """
    return await agentic_query(
        prompt=f"""Analyze playtest results in {playtest_dir}:

## Step 1: Run Statistical Analysis
Bash: python scripts/compute_stats.py {playtest_dir} --output stats.json

## Step 2: Read Intended Mechanics
Read: GAME_MANUAL.md (focus on variance formula, settlement rules, ending conditions)

## Step 3: Read Statistical Results
Read: stats.json

## Step 4: Analyze for Issues
Check each metric against intended behavior:
- Dominant strategy: any pairing with >70% win rate?
- Variance calibration: VP standard deviation in 15-25 range?
- Settlement rate: between 40-60%?
- Crisis termination: does uncertain ending prevent backward induction?

## Step 5: Produce Report
Write analysis report with:
- Executive Summary (1-2 paragraphs)
- Statistical Tables (from stats.json)
- Issue List (Critical/Major/Minor severity)
- Recommended Changes (specific code/parameter changes)
- Successful Mechanics (what's working)""",
        allowed_tools=["Bash", "Read", "Write", "Glob"],
        max_turns=20,
    )
```

**Statistical Analysis Script** (`scripts/compute_stats.py`):
```python
# Pure Python statistical analysis - no LLM
# Computes:
# - Win rates per pairing
# - VP distributions (mean, std, percentiles)
# - Turn length distribution
# - Ending type breakdown
# - Settlement rate and timing
# - Cooperation score trajectories
# Outputs structured JSON for agent to interpret
```

**Implementation Tasks**:
1. Implement `scripts/compute_stats.py` (pure Python, no LLM)
2. Create `MECHANICS_ANALYSIS_SYSTEM_PROMPT` in `prompts.py`
3. Agent uses **Bash tool** to run statistical scripts
4. Agent uses **Read tool** to examine GAME_MANUAL.md and stats output
5. Agent uses **Write tool** to produce analysis report
6. LLM interprets statistical patterns (but doesn't compute them)

**Acceptance Criteria**:
- [ ] Agent runs statistical analysis via Bash tool (not LLM math)
- [ ] Agent reads GAME_MANUAL.md for reference (Read tool)
- [ ] Analysis compares actual stats against intended metrics
- [ ] Issue detection uses statistical thresholds (>70% win rate, etc.)
- [ ] Recommendations are specific: "Change variance factor from X to Y"
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

## Phase 9: Playtesting and Iteration (Full Agentic Workflow)

### Milestone 9.1: Playtest Orchestration Agent

**Deliverable**: `scripts/full_playtest.py` - Agentic orchestrator for comprehensive playtesting

**Design Principle**: The playtest workflow is a **fully autonomous agentic loop** that uses tools to:
1. Generate scenarios (LLM + validation scripts)
2. Run game simulations (Bash tool → Python scripts)
3. Analyze results (Bash tool → statistics scripts + LLM interpretation)
4. Produce actionable reports (Write tool)

**Full Agentic Workflow Implementation**:
```python
from brinksmanship.llm import agentic_query

PLAYTEST_ORCHESTRATION_PROMPT = """
# Playtest Analysis Task (Agentic Workflow)

You have full tool access. Execute each step using the appropriate tool.

## Phase 1: Setup (Read Tools)
1. Read GAME_MANUAL.md - understand intended mechanics
2. Read src/brinksmanship/prompts.py - understand persona definitions
3. Glob src/brinksmanship/engine/*.py - identify implementation files

## Phase 2: Scenario Generation (Bash + Write Tools)
For each theme in [Cold War, Corporate, Ancient]:
1. Bash: python scripts/generate_scenario.py --theme "{theme}" --output scenarios/{theme}.json
2. Bash: python scripts/quick_validate.py scenarios/{theme}.json
3. If validation fails, regenerate with feedback

## Phase 3: Batch Playtesting (Bash Tool - Parallel Execution)
For each scenario, run these commands:
```
# Deterministic opponents (no LLM needed - fast)
Bash: python scripts/run_playtest.py \
    --scenario scenarios/{theme}.json \
    --pairings "Nash:Nash,TitForTat:Opportunist,SecuritySeeker:GrimTrigger,TitForTat:GrimTrigger" \
    --games 50 \
    --output results/{theme}_deterministic.json

# Historical personas (requires LLM - slower)
Bash: python scripts/run_playtest.py \
    --scenario scenarios/{theme}.json \
    --pairings "Bismarck:Khrushchev,Buffett:Icahn,Welch:Dimon" \
    --games 20 \
    --output results/{theme}_personas.json

# Simulated humans
Bash: python scripts/run_playtest.py \
    --scenario scenarios/{theme}.json \
    --human-sim \
    --games 30 \
    --output results/{theme}_human_sim.json
```

## Phase 4: Statistical Analysis (Bash + Read Tools)
1. Bash: python scripts/compute_stats.py results/ --output results/aggregate_stats.json
2. Read: results/aggregate_stats.json
3. Check thresholds:
   - Dominant strategy: any pairing >70% win rate? → CRITICAL
   - VP std dev outside 15-25 range? → MAJOR
   - Settlement rate outside 40-60%? → MAJOR
   - Average turns < 8 or > 15? → MINOR

## Phase 5: Analysis Questions (LLM Interpretation of Data)
Using the statistical data from Phase 4, answer:

1. **Dominant Strategies**: Check aggregate_stats.json win rates. If Nash:Nash
   always wins, that's a problem. If win rates are 45-55%, mechanics are balanced.

2. **Variance Calibration**: Check vp_std_dev field. Compare to intended 15-25.

3. **Settlement Incentives**: Check settlement_rate field. Compare to 40-60% target.

4. **Historical Personas**: Check persona pairing results. Do they match
   documented patterns? (e.g., Buffett should rarely initiate aggression)

## Phase 6: Report Generation (Write Tool)
Write: reports/playtest_analysis.md

Include:
1. Executive Summary (2-3 paragraphs)
2. Statistical Tables (formatted from JSON data)
3. Issue List with severity and statistical evidence
4. Recommended Changes with specific parameter values
5. Successful Mechanics with supporting data
"""

async def run_full_playtest():
    """Run complete playtest analysis autonomously."""
    return await agentic_query(
        prompt=PLAYTEST_ORCHESTRATION_PROMPT,
        allowed_tools=["Read", "Write", "Bash", "Glob", "Grep", "Task"],
        max_turns=50,  # Allow for comprehensive analysis
    )
```

**Tool Usage Summary**:
| Phase | Tools Used | Purpose |
|-------|-----------|---------|
| Setup | Read, Glob | Understand codebase and rules |
| Generation | Bash | Run scenario generation scripts |
| Playtesting | Bash | Run game simulation scripts (parallel) |
| Statistics | Bash, Read | Compute and read statistical results |
| Analysis | (LLM reasoning) | Interpret statistical patterns |
| Reporting | Write | Produce final report |

**Key Principle**: LLM reasoning is used ONLY for:
- Interpreting statistical patterns
- Making qualitative judgments about persona behavior
- Writing human-readable reports

All numerical analysis, game execution, and data aggregation happens via **deterministic Python scripts** invoked through the Bash tool.

**Acceptance Criteria**:
- [ ] Agent executes complete workflow autonomously
- [ ] All game simulations run via Bash tool (deterministic)
- [ ] Statistical analysis runs via Bash tool (not LLM math)
- [ ] LLM interprets results but doesn't compute them
- [ ] Final report includes statistical evidence for all claims
- [ ] Issues are actionable: "Change variance_factor from 1.2 to 1.0"
- [ ] Workflow completes in under 30 minutes for standard test suite

---

## SDK Reference

### Claude Agent SDK Usage

**Installation**:
```bash
pip install claude-agent-sdk
```

### Using the LLM Utilities (Recommended)

This project provides `src/brinksmanship/llm.py` which wraps the Claude Agent SDK with convenient utilities.

**Basic Text Generation** (no tools):
```python
from brinksmanship.llm import generate_text, generate_json

# Simple text generation
response = await generate_text(
    prompt="What is game theory?",
    system_prompt="You are a game theory expert. Be concise."
)

# Structured JSON output
scenario = await generate_json(
    prompt="Generate a game scenario with title and description.",
    system_prompt="Output valid JSON only, no markdown."
)
```

**Agentic Queries** (with tool access):
```python
from brinksmanship.llm import agentic_query

# Research with WebSearch
persona_data = await agentic_query(
    prompt="Research Otto von Bismarck's negotiation style for a game AI.",
    allowed_tools=["WebSearch", "WebFetch"],
    max_turns=15,
)

# Run Python scripts with Bash
validation_result = await agentic_query(
    prompt="Validate scenario: python scripts/quick_validate.py test.json",
    allowed_tools=["Bash", "Read"],
)

# Full agentic workflow with multiple tools
playtest_report = await agentic_query(
    prompt="""Run playtest analysis:
1. Bash: python scripts/run_playtest.py --scenario test.json --games 50
2. Read: playtest_results.json
3. Analyze results for dominant strategies
4. Write: reports/analysis.md""",
    allowed_tools=["Bash", "Read", "Write", "Glob"],
    max_turns=30,
)
```

**LLMClient Class** (for consistent configuration):
```python
from brinksmanship.llm import LLMClient

# Create client with defaults
client = LLMClient(
    system_prompt="You are a game designer specializing in game theory.",
    allowed_tools=["Read", "Bash"],
)

# Use client methods
response = await client.generate("Design a payoff matrix")
scenario = await client.generate_json("Create a scenario as JSON")
result = await client.agentic("Run: python scripts/validate.py scenario.json")
```

### Direct SDK Usage (Advanced)

For advanced use cases, use the SDK directly:

**Tool-Enabled Query**:
```python
from claude_agent_sdk import query, ClaudeAgentOptions

async def validate_scenario_with_tools(scenario_path: str):
    options = ClaudeAgentOptions(
        allowed_tools=["Read", "Bash", "Write"],
        system_prompt="You are a game balance validator.",
        max_turns=20,
    )

    async for message in query(
        prompt=f"Validate {scenario_path} by running python scripts/quick_validate.py",
        options=options
    ):
        if hasattr(message, 'result'):
            return message.result
```

**Subagent Orchestration**:
```python
from claude_agent_sdk import query, ClaudeAgentOptions, AgentDefinition

async def run_parallel_tests():
    options = ClaudeAgentOptions(
        allowed_tools=["Bash", "Read", "Task"],
        agents={
            "validator": AgentDefinition(
                description="Validates scenario files",
                prompt="Run validation scripts and report issues.",
                tools=["Bash", "Read"]
            ),
            "researcher": AgentDefinition(
                description="Researches historical figures",
                prompt="Use web search to find documented behaviors.",
                tools=["WebSearch", "WebFetch"]
            ),
        }
    )

    async for message in query(
        prompt="Spawn validator for scenario.json and researcher for Bismarck in parallel.",
        options=options
    ):
        yield message
```

### Available Tools

| Tool | Description | Use Case |
|------|-------------|----------|
| **Read** | Read file contents | Load scenarios, configs, results |
| **Write** | Create/overwrite files | Generate reports, cache data |
| **Edit** | Modify existing files | Update configurations |
| **Bash** | Execute shell commands | Run Python scripts, git ops |
| **Glob** | Find files by pattern | Discover test files, scenarios |
| **Grep** | Search file contents | Find code patterns |
| **WebSearch** | Search the web | Research historical figures |
| **WebFetch** | Fetch web page content | Extract detailed information |
| **Task** | Spawn subagents | Parallel task execution |

### Tool Selection Guidelines

| Task Type | Recommended Tools | Why |
|-----------|-------------------|-----|
| Scenario validation | Bash, Read | Run deterministic Python scripts |
| Persona research | WebSearch, WebFetch | Ground in documented behavior |
| Playtest execution | Bash | Run game simulations |
| Statistical analysis | Bash, Read | Compute stats via Python |
| Report generation | Read, Write | Interpret data, write reports |
| Parallel testing | Task, Bash | Subagents for concurrent work |

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
    "claude-agent-sdk>=0.1.0",  # NEVER use plain anthropic API directly
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

**Week 1**: Phase 1 (Models + Storage) + Phase 2.1-2.2 (Core Engine)
**Week 2**: Phase 2.3-2.4 (Variance, Endings) + Phase 3 (Scenario Generation)
**Week 3**: Phase 4 (Opponents)
**Week 4**: Phase 5 (Playtesting) + Phase 6 (Coaching)
**Week 5**: Phase 7 (CLI) + Phase 8 (Integration)
**Week 6**: Phase 9 (Playtesting and Iteration)

Note: Milestone 1.4 (Storage Repository) is foundational infrastructure used by both the CLI and webapp. It should be completed early to enable parallel webapp development.

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
