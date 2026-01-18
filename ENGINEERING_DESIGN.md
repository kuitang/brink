# Brinksmanship: Engineering Design Document

## Implementation Guide for Claude Code

---

## Overview

This document provides an implementation plan for Brinksmanship, a game-theoretic strategy simulation.

**Target Runtime**: Python 3.11+
**LLM Integration**: Claude Agent SDK for personas and settlement evaluation
**CLI Framework**: Textual
**Storage**: SQLite (webapp), JSON files (CLI)
**Validation/Testing**: Deterministic Python scripts (no LLM orchestration)

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
- [x] `GameState` contains: position_a, position_b, resources_a, resources_b, cooperation_score, stability, risk_level, turn, previous_type_a, previous_type_b
- [x] All numeric fields are clamped to valid ranges on assignment
- [x] State can be serialized to JSON and deserialized without loss
- [x] State includes computed properties for variance calculation
- [x] Unit tests pass for all state transitions

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
- [x] `MatrixParameters.__post_init__` rejects invalid parameter combinations
- [x] Each constructor enforces ordinal constraints (cannot produce invalid matrix)
- [x] `PayoffMatrix` is never serialized; only `(MatrixType, MatrixParameters)` pairs persist
- [x] Unit tests: random valid parameters always produce correct ordinal structure
- [x] Unit tests: verify Nash equilibria match expected (computed once at test time)
- [x] No runtime Nash equilibrium computation exists in codebase

### Milestone 1.3: Action Definitions

**Deliverable**: `src/brinksmanship/models/actions.py`

**Implementation Tasks**:
1. Define `Action` dataclass with name, type, resource_cost, description
2. Define action menus for each Risk Level tier (1-3, 4-6, 7-9)
3. Implement action classification (Cooperative vs Competitive)
4. Implement action-to-matrix-choice mapping
5. Define special actions (Settlement, Reconnaissance)

**Acceptance Criteria**:
- [x] Actions are correctly classified as COOPERATIVE or COMPETITIVE
- [x] Action menus vary by Risk Level as specified in GAME_MANUAL.md
- [x] Resource costs are enforced (cannot take action if insufficient resources)
- [x] Settlement action has special handling (bypasses matrix resolution)
- [x] Unit tests verify action classification

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
- [x] `ScenarioRepository` interface defined with list/get/save/delete
- [x] `FileScenarioRepository` reads/writes JSON files
- [x] `SQLiteScenarioRepository` uses sqlite3 (simplified from SQLAlchemy)
- [x] `GameRecordRepository` interface defined
- [x] Both backends pass identical integration tests
- [x] Factory function returns correct backend based on config
- [x] CLI and webapp use repository, not direct file access

### Milestone 1.5: InformationState Model

**Deliverable**: Addition to `src/brinksmanship/models/state.py`

**Design Principle**: Information is acquired through strategic games, not passive observation. Information decays over time as opponent state changes. This model tracks what each player knows about their opponent (see GAME_MANUAL.md Section 3.6).

**Implementation Tasks**:
1. Define `InformationState` dataclass for tracking knowledge about opponent
2. Implement position estimate calculation with decay
3. Implement resources estimate calculation with decay
4. Integrate with GameState to track per-player information states

**InformationState Definition**:
```python
@dataclass
class InformationState:
    """What one player knows about the other."""
    position_bounds: tuple[float, float] = (0.0, 10.0)
    resources_bounds: tuple[float, float] = (0.0, 10.0)
    known_position: Optional[float] = None
    known_position_turn: Optional[int] = None
    known_resources: Optional[float] = None
    known_resources_turn: Optional[int] = None

    def get_position_estimate(self, current_turn: int) -> tuple[float, float]:
        """Returns (estimate, uncertainty_radius)."""
        if self.known_position is not None:
            turns_elapsed = current_turn - self.known_position_turn
            uncertainty = min(turns_elapsed * 0.8, 5.0)
            return self.known_position, uncertainty
        else:
            midpoint = sum(self.position_bounds) / 2
            radius = (self.position_bounds[1] - self.position_bounds[0]) / 2
            return midpoint, radius
```

**Acceptance Criteria**:
- [x] `InformationState` dataclass defined with all fields
- [x] `get_position_estimate` returns (estimate, uncertainty_radius)
- [x] Uncertainty grows at 0.8 per turn, capped at 5.0
- [x] Initial bounds are (0.0, 10.0) for both position and resources
- [x] Information from successful Reconnaissance/Inspection games can update known values
- [x] Unit tests verify decay calculation

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
6. Implement information game system (see GAME_MANUAL.md Section 3.6)

**Acceptance Criteria**:
- [x] Engine loads scenario from JSON file
- [x] Turn sequence follows exact 8-phase structure from GAME_MANUAL.md
- [x] Cooperation Score updates correctly: CC→+1, DD→-1, mixed→0
- [x] Stability updates correctly based on switch count
- [x] Information games (Reconnaissance, Inspection) implemented per GAME_MANUAL.md Section 3.6
- [x] Information state tracking with decay (uncertainty = turns_elapsed × 0.8, max 5.0)
- [x] Complete turn history is available for coaching

### Milestone 2.2: Resolution System

**Deliverable**: `src/brinksmanship/engine/resolution.py`

**Implementation Tasks**:
1. Implement matrix resolution for simultaneous actions
2. Implement action-to-matrix-choice mapping
3. Implement payoff application to state
4. Implement settlement negotiation logic
5. Implement reconnaissance game (information as game)

**Acceptance Criteria**:
- [x] Matrix resolution uses hidden payoff values from scenario
- [x] Payoffs are scaled by Act Multiplier (0.7×, 1.0×, 1.3×)
- [x] Settlement constraints are enforced (VP ranges based on Position)
- [x] Reconnaissance resolves as Matching Pennies variant
- [x] Resolution returns complete `ActionResult` with all changes

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
act_multiplier = {1: 0.7, 2: 1.0, 3: 1.3}[act]
shared_sigma = base_sigma * chaos_factor * instability_factor * act_multiplier
```

**Acceptance Criteria**:
- [x] `Shared_σ` stays in range 10-40 for all valid states
- [x] Symmetric renormalization: both players clamped, then normalized to sum to 100
- [x] VP sum to 100 exactly after renormalization
- [x] Unit tests verify: peaceful ~10σ, neutral ~19σ, tense ~27σ, crisis ~37σ

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
- [x] Risk=10 triggers Mutual Destruction (both get 20 VP)
- [x] Position=0 triggers loss (10 VP) for that player
- [x] Resources=0 triggers loss (15 VP) for that player
- [x] Crisis Termination probability = (Risk - 7) × 0.08 for Risk > 7
- [x] Crisis Termination only checked for Turn >= 10
- [x] Max turn range: 12-16 (hidden from players)

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
- [x] StateDeltas dataclass with pos_a, pos_b, res_cost_a, res_cost_b, risk_delta
- [x] Templates defined for all 14 viable game types
- [x] Validation rejects out-of-bounds deltas
- [x] Validation enforces ordinal consistency (T > R > P > S for PD)
- [x] Act scaling correctly applied to deltas

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
      "action_menu": ["action1", "action2"],
      "outcome_narratives": {
        "CC": "string",
        "CD": "string",
        "DC": "string",
        "DD": "string"
      },
      "branches": {
        "CC": "turn_2a",
        "CD": "turn_2b",
        "DC": "turn_2b",
        "DD": "turn_2c"
      },
      "default_next": "turn_2b",
      "settlement_available": true,
      "settlement_failed_narrative": "Negotiations collapsed. The crisis remains unresolved."
    }
  ],
  "branches": {
    "turn_2a": { ... },
    "turn_2b": { ... },
    "turn_2c": { ... }
  }
}
```

**What is NOT in the schema**:
- `matrix_payoffs` — raw payoffs are never stored (computed from constructor)
- `state_deltas` — computed from constructor at load time based on matrix type

**What IS in the schema** (new for settlement mechanics):
- `default_next` — branch to follow if settlement fails or turn is skipped
- `settlement_available` — whether settlement can be proposed this turn
- `settlement_failed_narrative` — narrative text for failed settlement

**Load-Time Behavior**:
When a scenario is loaded, for each turn:
1. Parse `matrix_type` and `matrix_parameters`
2. Validate parameters via `MatrixParameters.__post_init__`
3. Call `CONSTRUCTORS[matrix_type].build(params)` to get `PayoffMatrix`
4. Store constructed matrix in memory (not persisted)

If any parameter validation or construction fails, the scenario load fails with a clear error.

**Acceptance Criteria**:
- [x] Schema has no field for raw payoffs
- [x] Schema enforces `matrix_parameters` ranges via Pydantic validators
- [x] Schema supports branching structure
- [x] Loading a scenario automatically constructs matrices
- [x] Invalid parameter combinations fail at load time with clear errors
- [x] Scenario round-trips: save → load → save produces identical JSON

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
- [x] Generator uses `claude-agent-sdk` for LLM calls
- [x] LLM never outputs raw payoffs, only types and parameters
- [x] All generated parameters pass validation before storage
- [x] Generated scenarios use 8+ distinct matrix types
- [x] Generated scenarios have 12-16 turn maximum (randomized)
- [x] Three-act structure reflected in game type and parameter choices
- [x] Generated scenarios load successfully (matrices construct without error)

### Milestone 3.3: Scenario Validator (Deterministic Python)

**Deliverable**: `src/brinksmanship/generation/validator.py` and `scripts/validate_scenario.py`

**Design Principle**: Matrix correctness is guaranteed by construction. The validator uses **deterministic Python scripts** for all checks—no agentic orchestration needed. LLM is used only for narrative consistency (optional).

**What is NO LONGER validated** (guaranteed by constructors):
- ~~Payoffs match game type~~ — impossible to fail
- ~~Nash equilibria exist~~ — guaranteed by ordinal constraints
- ~~Ordinal constraints hold~~ — enforced by constructor
- ~~Payoff symmetry for symmetric games~~ — constructor responsibility

**What IS validated**:
1. **Game type variety**: ≥8 distinct types across scenario (deterministic check)
2. **Act structure compliance**: Turns map to correct acts (deterministic check)
3. **Balance analysis**: Run game simulations to detect dominant strategies
4. **Branching structure**: All branches have valid targets, default_next exists
5. **Narrative consistency**: Optional LLM check for thematic coherence

**Validation Script** (`scripts/validate_scenario.py`):
```python
#!/usr/bin/env python3
"""Deterministic scenario validation - no LLM required for core checks."""

def validate_scenario(scenario_path: str) -> ValidationResult:
    """Run all validation checks on a scenario.

    Returns structured result with pass/fail for each check.
    """
    scenario = load_scenario(scenario_path)

    results = ValidationResult()

    # 1. Structural checks (pure Python)
    results.game_variety = check_game_variety(scenario)  # ≥8 types
    results.act_structure = check_act_structure(scenario)  # Turns in correct acts
    results.branching = check_branching_validity(scenario)  # All branches valid
    results.settlement = check_settlement_config(scenario)  # default_next exists

    # 2. Balance simulation (pure Python)
    sim_results = run_balance_simulation(scenario, games=50)
    results.balance = check_dominant_strategy(sim_results)  # No >60% win rate

    # 3. Optional: Narrative consistency (requires LLM)
    if args.check_narrative:
        results.narrative = check_narrative_consistency(scenario)

    return results

# CLI usage:
# python scripts/validate_scenario.py scenarios/cold_war.json
# python scripts/validate_scenario.py scenarios/cold_war.json --check-narrative
```

**Implementation Tasks**:
1. Implement `ScenarioValidator` class (pure Python, no LLM)
2. Implement `scripts/validate_scenario.py` (CLI entry point)
3. Implement structural checks (variety, acts, branching)
4. Implement balance simulation runner
5. Implement dominant strategy detection (>60% win rate = fail)
6. Optional: Add `--check-narrative` flag for LLM narrative check

**Acceptance Criteria**:
- [x] Validator does NOT use LLM to reason about game theory or balance
- [x] Balance analysis runs 50+ actual game simulations
- [x] CLI returns structured JSON with pass/fail for each check
- [x] Dominant strategy check fails if any pairing >60% win rate
- [x] All checks complete in <30 seconds
- [x] Dominant strategy detection: statistical threshold (>60% win rate), not LLM judgment
- [x] Game type variety check: deterministic Python code
- [x] Act structure check: deterministic Python code
- [x] LLM checks focus on narrative consistency ONLY
- [x] Validation is fast for structural checks (< 100ms)
- [x] Validation report includes statistical tables from simulations

---

## Phase 4: Opponent System

### Milestone 4.1: Base Opponent Interface

**Deliverable**: `src/brinksmanship/opponents/base.py`

**Implementation Tasks**:
1. Define `Opponent` abstract base class
2. Define `choose_action` method signature
3. Define `receive_result` method for learning
4. Define `evaluate_settlement` method for settlement negotiations
5. Implement opponent factory function

**Settlement Interface**:
```python
@dataclass
class SettlementProposal:
    """A settlement proposal with numeric offer and argument."""
    offered_vp: int  # VP proposed for the proposer (0-100)
    argument: str    # Free-text rationale (max 500 chars)

@dataclass
class SettlementResponse:
    """Response to a settlement proposal."""
    action: Literal["accept", "counter", "reject"]
    counter_vp: Optional[int] = None  # If countering
    counter_argument: Optional[str] = None
    rejection_reason: Optional[str] = None

class Opponent(ABC):
    @abstractmethod
    def choose_action(self, state: GameState, available_actions: list[Action]) -> Action:
        """Choose strategic action for this turn."""
        pass

    @abstractmethod
    def evaluate_settlement(
        self,
        proposal: SettlementProposal,
        state: GameState,
        is_final_offer: bool
    ) -> SettlementResponse:
        """Evaluate a settlement proposal and respond.

        NOTE: Even deterministic opponents use LLM for this method,
        as the argument text requires language understanding.
        """
        pass

    @abstractmethod
    def propose_settlement(self, state: GameState) -> Optional[SettlementProposal]:
        """Optionally propose settlement. Returns None if not proposing."""
        pass
```

**Acceptance Criteria**:
- [x] All opponents implement the same interface
- [x] Interface supports both human and AI opponents
- [x] `evaluate_settlement` processes both numeric offer AND argument text
- [x] Factory function creates opponent by type name

### Milestone 4.2: Deterministic Opponents

**Deliverable**: `src/brinksmanship/opponents/deterministic.py`

**Design Principle**: Deterministic opponents use algorithmic rules for strategic actions (Cooperate/Defect), but use **LLM for settlement evaluation**. The argument text in settlement proposals requires language understanding that pure algorithms cannot provide.

**Implementation Tasks**:
1. Implement `NashCalculator` opponent (plays Nash equilibrium)
2. Implement `SecuritySeeker` opponent (Spiral model actor)
3. Implement `Opportunist` opponent (Deterrence model actor)
4. Implement `Erratic` opponent (randomized behavior)
5. Implement `TitForTat` opponent (Axelrod's strategy)
6. Implement `GrimTrigger` opponent (defect forever after betrayal)

**Opponent Type Specifications**:

| Type | Description | Strategic Pattern | Settlement Tendency |
|------|-------------|-------------------|---------------------|
| NashCalculator | Pure game theorist | Plays Nash equilibrium | Accepts if offer ≥ position-fair value |
| SecuritySeeker | Spiral model actor | Escalates only when threatened | Prefers settlement, accepts generous offers |
| Opportunist | Deterrence model actor | Probes for weakness | Rejects unless dominant, exploits weak arguments |
| Erratic | Unpredictable | Mixes strategies with noise | Unpredictable acceptance |
| TitForTat | Reciprocator | Mirrors opponent's last move | Accepts fair offers from cooperative opponents |
| GrimTrigger | Punisher | Defects forever after betrayal | Never accepts after betrayal |

**Settlement Evaluation (LLM-based)**:
```python
class DeterministicOpponent(Opponent):
    def evaluate_settlement(self, proposal, state, is_final_offer):
        # Even deterministic opponents use LLM for settlement
        # The persona prompt shapes how the LLM evaluates arguments
        return await evaluate_settlement_with_llm(
            proposal=proposal,
            state=state,
            persona_prompt=self.settlement_persona_prompt,
            is_final_offer=is_final_offer
        )

    # But strategic actions remain deterministic
    def choose_action(self, state, actions):
        return self._deterministic_choice(state, actions)
```

**Acceptance Criteria**:
- [x] Strategic actions are purely deterministic (testable, reproducible)
- [x] Settlement evaluation uses LLM with persona-specific prompts
- [x] Opponents use only observable game state (no cheating)
- [x] Unit tests verify strategic behavior patterns
- [x] Settlement behavior matches persona descriptions

### Milestone 4.3: Historical Personas (LLM-based)

**Deliverable**: `src/brinksmanship/opponents/historical.py` and `src/brinksmanship/opponents/personas/`

**Design Principle**: Persona definitions are grounded in documented historical behavior. For well-known figures (Bismarck, Khrushchev, etc.), the LLM's training data is sufficient. No WebSearch is needed—LLM knowledge covers all included personas.

**Implementation Tasks**:
1. Implement `HistoricalPersona` class using Claude Agent SDK
2. Define persona prompt templates in `prompts.py` (include characteristic quotes)
3. Implement persona library with the following figures:

**Political/Military Personas (Pre-20th Century)**:
- **Otto von Bismarck**: Realpolitik, flexible alliances, never fights unwinnable wars
- **Cardinal Richelieu**: Raison d'état, long game, weakens rivals through proxies
- **Metternich**: Concert of Europe, stability over hegemony, endless negotiation
- **Pericles** (Athens): Defensive grand strategy, avoids pitched battles, leverages naval superiority, manages alliance through soft power, patient attrition

**Cold War / Small State Personas**:
- **Richard Nixon**: Triangular diplomacy, exploits rival divisions, pragmatic dealmaker, comfortable with ambiguity, "madman theory" unpredictability
- **Henry Kissinger**: Realpolitik architect, linkage diplomacy, balance of power, prefers stability over ideology, back-channel negotiations
- **Nikita Khrushchev**: Probes for weakness, bold gestures, backs down if opponent holds firm, brinkmanship but knows limits
- **Josip Broz Tito**: Non-alignment, plays superpowers against each other, builds third-world coalitions, leverages unique position, fiercely independent
- **Urho Kekkonen** (Finland): "Finlandization" - survival through strategic accommodation, "bowing to the East without mooning the West", preserves independence through perceived compliance
- **Lee Kuan Yew** (Singapore): Small state survival, cold realpolitik assessment, balance of power engagement, exceptionalism, makes self indispensable to larger powers

**Corporate/Tech Personas** (selected for documented evidence from lawsuits, depositions, internal emails):
- **Bill Gates**: Predatory competitor, leverages market dominance, bundles/forecloses, "cut off their air supply", evasive when cornered (Microsoft antitrust trial emails)
- **Steve Jobs**: Hard-nosed negotiator, confident silence, walk-away credibility, social proof leverage, lays out opponent's options unfavorably (DOJ ebook lawsuit emails)
- **Carl Icahn**: Corporate raider, hostile pressure, proxy fights, greenmail, finds unexpected allies (e.g., unions at TWA), exploits weakness
- **Mark Zuckerberg**: Strategic acquirer, "buy or bury", identifies threats early, neutralizes competition through acquisition without creating market holes (FTC antitrust emails)
- **Warren Buffett**: Patient cooperator, reputation for fairness, avoids hostile actions, "favorite holding period is forever", strong from prepared position, contrarian in crisis

**Palace Intrigue Personas**:
- **Empress Theodora** (Byzantine): Rose from actress to co-ruler, "purple makes the best shroud", stands firm in crisis, champions her faction, ruthless when threatened but builds genuine loyalty
- **Wu Zetian** (Tang China): Only female Emperor of China, rose from concubine through intelligence and elimination of rivals, merit-based promotions, extensive spy networks, patient but decisive
- **Empress Dowager Cixi** (Qing China): De facto ruler for 47 years, masterful at playing factions, controls through regency and influence, modernizes selectively, consolidates power through perceived weakness
- **Livia Drusilla** (Rome): Wife of Augustus, exercises immense influence without formal power, patient multi-decade strategy, rumored poisoner (probably unjust), maintains appearances while controlling outcomes

4. Implement persona prompt that includes:
   - Historical context and worldview
   - Characteristic decision-making patterns
   - Known strategic preferences
   - Current game state
   - Action options

5. Implement `generate_new_persona` function using LLM

**Acceptance Criteria**:
- [x] Each persona has documented historical basis
- [x] Persona prompts are in `prompts.py`
- [x] LLM responses are parsed to valid actions
- [x] Personas maintain consistent behavior within a game
- [x] Unit tests verify personas make reasonable choices

### Milestone 4.4: Custom Persona Generator (LLM-based)

**Deliverable**: `src/brinksmanship/opponents/persona_generator.py` and addition to `prompts.py`

**Design Principle**: New personas can be created from a figure name/description.
- **Famous figures** (Bismarck, Gates, Buffett): LLM training data suffices (~5s)
- **Obscure/arbitrary figures**: WebSearch grounds persona in documented behavior (~30s)
- **Evaluation step**: Compare web-searched vs non-web-searched personas to validate quality

**Model Selection** (all use Claude Agent SDK):
- Research phase (WebSearch synthesis): **Opus** (extended thinking enabled automatically)
- Persona generation: **Opus** (extended thinking enabled automatically)
- Persona evaluation: **Opus** (requires nuanced judgment)

**Persona Generation with Evaluation** (using Claude Agent SDK):
```python
from claude_agent_sdk import query, ClaudeAgentOptions, AssistantMessage, TextBlock
import json

async def generate_persona(
    figure_name: str,
    use_web_search: bool = False,
    evaluate_quality: bool = True
) -> dict:
    """Generate a persona definition from a figure name.

    When evaluate_quality=True, generates both web-searched and non-web-searched
    versions and uses Opus to evaluate which is more detailed and accurate.
    """
    # Always generate baseline persona from training knowledge (Opus)
    options = ClaudeAgentOptions(
        model="opus",
        system_prompt=HISTORICAL_PERSONA_SYSTEM_PROMPT
    )

    baseline_text = ""
    async for message in query(
        prompt=PERSONA_GENERATION_PROMPT.format(figure_name=figure_name),
        options=options
    ):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    baseline_text += block.text

    baseline_persona = json.loads(baseline_text)

    if not use_web_search:
        return baseline_persona

    # Research phase: use WebSearch tool with Opus
    research_options = ClaudeAgentOptions(
        model="opus",
        allowed_tools=["WebSearch", "WebFetch"],
        system_prompt="Research this figure's strategic behavior, negotiation tactics, and documented decisions."
    )

    research_text = ""
    async for message in query(
        prompt=f"Research {figure_name}: find documented strategic decisions, negotiation tactics, quotes about strategy, emails/memos if available.",
        options=research_options
    ):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    research_text += block.text

    # Generate researched persona
    researched_text = ""
    async for message in query(
        prompt=PERSONA_GENERATION_PROMPT.format(
            figure_name=figure_name,
            research_context=research_text
        ),
        options=options
    ):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    researched_text += block.text

    researched_persona = json.loads(researched_text)

    if not evaluate_quality:
        return researched_persona

    # Evaluation step: compare both personas (Opus)
    eval_text = ""
    async for message in query(
        prompt=PERSONA_EVALUATION_PROMPT.format(
            figure_name=figure_name,
            baseline_persona=json.dumps(baseline_persona, indent=2),
            researched_persona=json.dumps(researched_persona, indent=2)
        ),
        options=options
    ):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    eval_text += block.text

    evaluation = json.loads(eval_text)

    return {
        "persona": researched_persona,
        "evaluation": evaluation,
        "web_search_beneficial": evaluation.get("web_search_added_value", False)
    }
```

**Evaluation Criteria** (PERSONA_EVALUATION_PROMPT):
- Does web search add specific quotes, dates, or decisions not in baseline?
- Does web search correct any factual errors in baseline?
- Does web search provide more nuanced strategic patterns?
- Is the researched persona more actionable for game decisions?

**When to use WebSearch**:
| Figure Type | Use WebSearch | Rationale |
|-------------|---------------|-----------|
| Famous historical (Bismarck, Napoleon) | Optional | LLM knows them well; evaluate to confirm |
| Famous tech/business (Gates, Jobs, Icahn) | Yes | Lawsuit emails add specific documented tactics |
| Fictional characters | No | LLM knows them from training |
| Obscure historical figures | Yes | LLM may have incomplete info |
| Contemporary figures (post-2024) | Yes | LLM cutoff may miss recent behavior |
| User-specified arbitrary person | Yes | Grounds persona in real data |

**Implementation Tasks**:
1. Implement `PersonaGenerator` class with `use_web_search` and `evaluate_quality` flags
2. Implement `web_search_persona_research()` targeting: strategic decisions, quotes, negotiation tactics, documented emails/memos
3. Create `PERSONA_GENERATION_PROMPT` with optional `research_context` field
4. Create `PERSONA_EVALUATION_PROMPT` for comparing baseline vs researched personas
5. Cache research results and evaluation outcomes
6. Log evaluation results to track which figures benefit from web search

**Acceptance Criteria**:
- [x] Personas include all required fields: worldview, patterns, risk, triggers, settlement_style
- [x] Evaluation step runs for new personas and logs whether web search added value
- [x] Famous figures (Gates, Jobs, etc.) show measurable improvement with web search due to lawsuit documentation
- [x] LLM-only path completes in <10 seconds
- [x] WebSearch path completes in <60 seconds
- [x] WebSearch results are cached by figure name

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
- [x] HumanPersona Pydantic model with all attributes (risk_tolerance, sophistication, emotional_state, personality) - TESTED
- [x] Mistake probability calculation (novice=30%, intermediate=15%, expert=5%, with emotional modifiers) - TESTED
- [x] Prompts added to prompts.py (HUMAN_SIMULATOR_SYSTEM_PROMPT, HUMAN_PERSONA_GENERATION_PROMPT, HUMAN_ACTION_SELECTION_PROMPT, MISTAKE_CHECK_PROMPT, HUMAN_SETTLEMENT_EVALUATION_PROMPT) - IMPLEMENTED
- [ ] Simulated humans make varied, realistic decisions - AWAITS LLM integration testing
- [ ] Different personas exhibit different play patterns - AWAITS LLM integration testing
- [ ] Simulated humans occasionally make suboptimal choices - AWAITS LLM integration testing
- [ ] Personas are generated fresh for each playtest session - AWAITS LLM integration testing

### Milestone 5.2: Playtester Framework (Deterministic Python)

**Deliverable**: `src/brinksmanship/testing/playtester.py` and `scripts/run_playtest.py`

**Design Principle**: The playtester is a **pure Python script** with no agentic orchestration. Parallelism is achieved through Python's `multiprocessing` or `asyncio`, not LLM subagents.

**Implementation Tasks**:
1. Implement `PlaytestRunner` class (pure Python)
2. Implement `scripts/run_playtest.py` for batch execution
3. Implement parallel game execution using `concurrent.futures`
4. Implement result aggregation from JSON outputs
5. Implement game log export

**Playtest Script** (`scripts/run_playtest.py`):
```python
#!/usr/bin/env python3
"""Deterministic playtest runner - no LLM orchestration needed."""

import argparse
from concurrent.futures import ProcessPoolExecutor

def run_playtest(scenario_path: str, pairings: list, games: int, output: str):
    """Run playtest with parallel game execution.

    Uses ProcessPoolExecutor for CPU-bound game simulation.
    """
    results = {}

    with ProcessPoolExecutor(max_workers=4) as executor:
        futures = {}
        for pairing in pairings:
            future = executor.submit(run_pairing, scenario_path, pairing, games)
            futures[pairing] = future

        for pairing, future in futures.items():
            results[pairing] = future.result()

    # Aggregate and write results
    aggregate = compute_aggregate_stats(results)
    write_json(output, {"pairings": results, "aggregate": aggregate})

# CLI usage:
# python scripts/run_playtest.py \
#     --scenario scenarios/cold_war.json \
#     --pairings "Nash:Nash,TitForTat:Opportunist" \
#     --games 100 \
#     --output playtest_results.json
```

**Output JSON structure**:
```json
{
  "pairings": {"Nash:Nash": {"wins_a": 45, "wins_b": 42, "ties": 13, ...}},
  "aggregate": {"avg_turns": 12.3, "settlement_rate": 0.52, ...},
  "logs": ["logs/game_001.json", "logs/game_002.json", ...]
}
```

**Acceptance Criteria**:
- [x] Pure Python game simulation with simplified state (SimpleGameState, SimplePlayerState) - TESTED
- [x] 7 built-in strategies (TitForTat, AlwaysDefect, AlwaysCooperate, Opportunist, Nash, GrimTrigger, Random) - TESTED
- [x] PlaytestRunner with run_pairing(), run_playtest(), run_all_pairings() - TESTED
- [x] Parallel execution via ProcessPoolExecutor - TESTED
- [x] Can run N games with specified opponent pairings - TESTED
- [x] Aggregates statistics: win rates, average VP, turn counts, ending types - TESTED
- [x] PairingStats and PlaytestResults dataclasses with to_dict/to_json - TESTED
- [x] run_playtest.py CLI with argparse (--pairings, --games, --output, --workers, --seed) - IMPLEMENTED
- [ ] Full integration with game engine (uses simplified simulation, not full GameState) - AWAITS game engine integration
- [ ] Scenario loading from JSON files - AWAITS scenario system

### Milestone 5.3: Mechanics Analysis (Deterministic Python)

**Deliverable**: `scripts/analyze_mechanics.py`

**Design Principle**: Mechanics analysis is **deterministic Python** with threshold-based issue detection. No LLM reasoning needed for statistical analysis—the script flags issues when metrics fall outside expected ranges.

**Analysis Script** (`scripts/analyze_mechanics.py`):
```python
#!/usr/bin/env python3
"""Deterministic mechanics analysis - threshold-based issue detection."""

# Expected ranges (from GAME_MANUAL.md)
THRESHOLDS = {
    "dominant_strategy": 0.60,  # Fail if any pairing >60% win rate
    "variance_min": 10,  # VP std dev should be ≥10
    "variance_max": 40,  # VP std dev should be ≤40
    "settlement_rate_min": 0.30,  # At least 30% settlements
    "settlement_rate_max": 0.70,  # At most 70% settlements
    "avg_game_length_min": 8,  # Games shouldn't be too short
    "avg_game_length_max": 16,  # Games shouldn't exceed max turns
}

def analyze_mechanics(playtest_results: dict) -> AnalysisReport:
    """Analyze playtest results against expected thresholds.

    Returns structured report with issues flagged.
    """
    report = AnalysisReport()

    # Check dominant strategy
    for pairing, stats in playtest_results["pairings"].items():
        if stats["win_rate_a"] > THRESHOLDS["dominant_strategy"]:
            report.add_issue("CRITICAL", f"Dominant strategy: {pairing} A wins {stats['win_rate_a']:.0%}")
        if stats["win_rate_b"] > THRESHOLDS["dominant_strategy"]:
            report.add_issue("CRITICAL", f"Dominant strategy: {pairing} B wins {stats['win_rate_b']:.0%}")

    # Check variance calibration
    vp_std = playtest_results["aggregate"]["vp_std_dev"]
    if vp_std < THRESHOLDS["variance_min"]:
        report.add_issue("MAJOR", f"Variance too low: {vp_std:.1f} (expected ≥{THRESHOLDS['variance_min']})")
    if vp_std > THRESHOLDS["variance_max"]:
        report.add_issue("MAJOR", f"Variance too high: {vp_std:.1f} (expected ≤{THRESHOLDS['variance_max']})")

    # Check settlement rate
    settlement_rate = playtest_results["aggregate"]["settlement_rate"]
    if settlement_rate < THRESHOLDS["settlement_rate_min"]:
        report.add_issue("MINOR", f"Settlement rate low: {settlement_rate:.0%}")
    if settlement_rate > THRESHOLDS["settlement_rate_max"]:
        report.add_issue("MINOR", f"Settlement rate high: {settlement_rate:.0%}")

    return report

# CLI usage:
# python scripts/analyze_mechanics.py playtest_results.json --output analysis.json
```

**Statistical Analysis Script** (`scripts/compute_stats.py`):
```python
#!/usr/bin/env python3
"""Pure Python statistical analysis - no LLM needed."""
# Computes:
# - Win rates per pairing
# - VP distributions (mean, std, percentiles)
# - Turn length distribution
# - Ending type breakdown
# - Settlement rate and timing
# - Cooperation score trajectories
# Outputs structured JSON
```

**Implementation Tasks**:
1. Implement `scripts/compute_stats.py` (pure Python)
2. Implement `scripts/analyze_mechanics.py` (threshold-based detection)
3. Implement `AnalysisReport` dataclass for structured output
4. Add JSON output with machine-readable issue list

**Acceptance Criteria**:
- [x] All analysis is pure Python with no LLM calls - TESTED
- [x] Issue detection uses statistical thresholds (DEFAULT_THRESHOLDS configurable) - TESTED
- [x] check_dominant_strategy (>60% win rate) - TESTED
- [x] check_variance_calibration (VP std dev 10-40) - TESTED
- [x] check_settlement_rate (30-70%) - TESTED
- [x] check_game_length (8-16 turns) - TESTED
- [x] AnalysisReport with Issue dataclass and severity levels (CRITICAL, MAJOR, MINOR) - TESTED
- [x] Output is structured JSON (to_dict, format_text_report) - TESTED
- [x] load_playtest_results from JSON file - TESTED
- [ ] Performance benchmark (<10 seconds for 100 games) - NOT BENCHMARKED

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
│ with unexpected proposals...                                    │
├─────────────────────────────────────────────────────────────────┤
│ YOUR STATUS (exact)    │ INTELLIGENCE ON OPPONENT               │
│ Position: 6.0          │ Position: UNKNOWN                      │
│ Resources: 4.2         │   Last recon: Turn 3, was 5.2          │
│                        │   Uncertainty: ±1.6 (2 turns stale)    │
│                        │   Estimate: 3.6 – 6.8                  │
│                        │ Resources: UNKNOWN                     │
│                        │   No inspection data                   │
├─────────────────────────────────────────────────────────────────┤
│ ACTIONS                                                         │
│ [1] Hold Position (Cooperative)                                 │
│ [2] Escalate Pressure (Competitive)                             │
│ [3] Propose Settlement (replaces action, Risk +1 if rejected)   │
│ [4] Initiate Reconnaissance (costs 0.5 Resources, replaces turn)│
│ [5] Signal Strength (costs 0.3-1.2 Resources, no turn cost)     │
├─────────────────────────────────────────────────────────────────┤
│ HISTORY: T1:CC | T2:CD | T3:Recon(success) | T4:CC              │
└─────────────────────────────────────────────────────────────────┘
```

**Settlement Proposal UI**:
```
┌─────────────────────────────────────────────────────────────────┐
│ PROPOSE SETTLEMENT                                              │
├─────────────────────────────────────────────────────────────────┤
│ Your suggested VP: 55 (based on position advantage)             │
│ Valid range: 45-65                                              │
│                                                                 │
│ Enter VP for yourself: [55]                                     │
│                                                                 │
│ Argument (max 500 chars):                                       │
│ ┌───────────────────────────────────────────────────────────┐   │
│ │ Our positions are roughly equal, but I've demonstrated    │   │
│ │ consistent good faith. The current risk level threatens   │   │
│ │ us both - a fair settlement protects our mutual interests.│   │
│ └───────────────────────────────────────────────────────────┘   │
│                                                                 │
│ [Enter] Submit  [Esc] Cancel                                    │
└─────────────────────────────────────────────────────────────────┘
```

**Acceptance Criteria**:
- [ ] Application launches and displays main menu
- [ ] All game state is clearly displayed
- [ ] Actions show type classification and resource cost
- [ ] Intelligence display shows information state with uncertainty bounds (per GAME_MANUAL.md Section 3.6.5)
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

# Historical Personas (Pre-20th Century)
HISTORICAL_PERSONA_SYSTEM_PROMPT = """..."""
PERSONA_BISMARCK = """..."""
PERSONA_RICHELIEU = """..."""
PERSONA_METTERNICH = """..."""
PERSONA_PERICLES = """..."""

# Cold War / Small State Personas
PERSONA_NIXON = """..."""
PERSONA_KISSINGER = """..."""
PERSONA_KHRUSHCHEV = """..."""
PERSONA_TITO = """..."""
PERSONA_KEKKONEN = """..."""
PERSONA_LEE_KUAN_YEW = """..."""

# Corporate/Tech Personas (selected for lawsuit/deposition documentation)
PERSONA_GATES = """..."""      # Microsoft antitrust trial emails
PERSONA_JOBS = """..."""       # DOJ ebook lawsuit emails
PERSONA_ICAHN = """..."""      # Decades of documented corporate raids
PERSONA_ZUCKERBERG = """...""" # FTC antitrust case emails
PERSONA_BUFFETT = """..."""    # Annual letters, documented philosophy

# Palace Intrigue Personas
PERSONA_THEODORA = """..."""
PERSONA_WU_ZETIAN = """..."""
PERSONA_CIXI = """..."""
PERSONA_LIVIA = """..."""

# Persona Generation & Evaluation
PERSONA_GENERATION_PROMPT = """..."""
PERSONA_EVALUATION_PROMPT = """..."""  # Compares baseline vs web-searched personas

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

## Phase 9: Playtesting Workflow

### Milestone 9.1: Playtest Pipeline

**Deliverable**: Shell scripts for running the complete playtest pipeline

**Workflow** (all deterministic Python, no LLM orchestration):
```bash
# 1. Generate scenarios
python scripts/generate_scenario.py --theme "Cold War" --output scenarios/cold_war.json

# 2. Validate scenarios
python scripts/validate_scenario.py scenarios/cold_war.json

# 3. Run playtests
python scripts/run_playtest.py --scenario scenarios/cold_war.json \
    --pairings "Nash:Nash,TitForTat:Opportunist" --games 100 --output results/

# 4. Analyze mechanics
python scripts/analyze_mechanics.py results/ --output analysis.json
```

**Thresholds** (from GAME_MANUAL.md):
- Dominant strategy: >60% win rate → CRITICAL
- VP std dev outside 10-40 range → MAJOR
- Settlement rate outside 30-70% → MAJOR
- Average turns < 8 or > 15 → MINOR

**Acceptance Criteria**:
- [ ] All scripts run without LLM calls (except persona opponents)
- [ ] Pipeline completes in <5 minutes for 100 games
- [ ] Analysis output is machine-readable JSON

---

## LLM Integration Reference

### Claude Agent SDK

**CRITICAL**: All LLM calls use the Claude Agent SDK (`claude-agent-sdk`), NOT the raw Anthropic API.

```bash
pip install claude-agent-sdk
```

### Model Selection Guide

**Principle**: Default to Opus for any reasoning task. Only use Sonnet for simple, high-volume tasks where latency/cost matters more than quality.

**Model Versions** (latest as of January 2026):
- **Opus 4.5**: `model="opus"` in ClaudeAgentOptions
- **Sonnet 4.5**: `model="sonnet"` in ClaudeAgentOptions

Extended thinking is enabled automatically by the SDK for supported models.

### Model Selection by Task

| Task | Model | Rationale |
|------|-------|-----------|
| **Persona Generation** | Opus | Complex synthesis of historical behavior |
| **Persona Research Synthesis** | Opus | Synthesizing web search into coherent profile |
| **Persona Evaluation** | Opus | Nuanced comparison of persona quality |
| **Scenario Generation** | Opus | Creative narrative + strategic game selection |
| **Settlement Evaluation** | Opus | Understanding argument quality, persona consistency |
| **Post-Game Coaching** | Opus | Deep analysis of game history and strategy |
| **Human Simulation** | Opus | Realistic human decision modeling |
| **Narrative Consistency Check** | Opus | Thematic coherence judgment |
| **Action Selection (Persona)** | Sonnet | High-volume, per-turn decision (latency-sensitive) |
| **Simple Parsing/Extraction** | Sonnet | Structured output from clear input |

### Claude Agent SDK Usage

```python
from claude_agent_sdk import query, ClaudeAgentOptions, AssistantMessage, TextBlock

# Opus for complex reasoning (persona generation, coaching, scenario design)
async def generate_with_opus(prompt: str, system_prompt: str = None) -> str:
    options = ClaudeAgentOptions(
        model="opus",
        system_prompt=system_prompt
    )

    result = ""
    async for message in query(prompt=prompt, options=options):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    result += block.text
    return result

# Sonnet for high-volume tasks (per-turn action selection)
async def generate_with_sonnet(prompt: str, system_prompt: str = None) -> str:
    options = ClaudeAgentOptions(
        model="sonnet",
        system_prompt=system_prompt
    )

    result = ""
    async for message in query(prompt=prompt, options=options):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    result += block.text
    return result

# With tools (e.g., WebSearch for persona research)
async def research_persona(figure_name: str) -> str:
    options = ClaudeAgentOptions(
        model="opus",
        allowed_tools=["WebSearch", "WebFetch"],
        system_prompt="Research strategic behavior and documented decisions."
    )

    result = ""
    async for message in query(
        prompt=f"Research {figure_name}: strategic decisions, negotiation tactics, documented emails/memos.",
        options=options
    ):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    result += block.text
    return result
```

### Subagent Definitions

For tasks requiring specialized agents, use `AgentDefinition`:

```python
from claude_agent_sdk import ClaudeAgentOptions, AgentDefinition

options = ClaudeAgentOptions(
    model="opus",
    agents={
        "persona-researcher": AgentDefinition(
            description="Research historical figures for persona creation",
            prompt="Research strategic behavior, negotiation tactics, and documented decisions.",
            tools=["WebSearch", "WebFetch"],
            model="opus"  # Use opus for research
        ),
        "action-selector": AgentDefinition(
            description="Select game actions based on persona",
            prompt="Choose the best action given current game state and persona.",
            tools=["Read"],
            model="sonnet"  # Use sonnet for high-volume per-turn decisions
        )
    }
)
```

**Use Cases Summary**:
| Component | Model | Purpose |
|-----------|-------|---------|
| Scenario Generator | Opus | Generate narrative briefings and action menus |
| Persona Opponents (action) | Sonnet | Choose actions based on persona prompt (high volume) |
| Persona Generation | Opus | Create new persona from figure name |
| Settlement Evaluation | Opus | Evaluate argument text for all opponent types |
| Post-Game Coaching | Opus | Analyze game history and provide feedback |
| Human Simulation | Opus | Model realistic human decision-making |
| Narrative Check | Opus | Verify thematic consistency |

**What Does NOT Use LLM**:
- Matrix construction (deterministic from parameters)
- State delta application (deterministic formulas)
- Ending condition checks (deterministic thresholds)
- Balance simulation (pure Python)
- Validation (pure Python with threshold checks)
- Playtest orchestration (pure Python multiprocessing)

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
