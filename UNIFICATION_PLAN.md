# Plan: Unify Balance Simulation, Playtester, and Regular Play

## Current Problem

We have **3 separate simulation systems** that duplicate game logic:

### 1. `scripts/balance_simulation.py` (778 lines)
- Custom `Action` enum (COOPERATE/DEFECT)
- Custom `PlayerState`, `GameState` dataclasses
- 8 simplified strategy functions (tit_for_tat, nash_aware, opportunist, etc.)
- Uses `get_scaled_delta_for_outcome` from `state_deltas.py` (GOOD)
- Custom game loop with manual ending checks
- **Problem**: Strategies don't match actual `DeterministicOpponent` implementations

### 2. `src/brinksmanship/testing/playtester.py` (1222 lines)
- Custom `ActionChoice` enum
- Custom `SimpleGameState`, `SimplePlayerState` dataclasses
- 7 simplified strategy functions
- **CRITICAL**: Hardcoded Prisoner's Dilemma deltas (ignores actual delta templates!)
- Custom game loop
- **Problem**: Completely disconnected from real game mechanics

### 3. `src/brinksmanship/testing/engine_playtester.py` (729 lines)
- Uses real `GameEngine` from `brinksmanship.engine.game_engine` (GOOD)
- Uses actual `GameState`, `Action`, `ActionType` from models (GOOD)
- Has `EngineStrategy` functions (simplified)
- Has `StrategyAdapter` to wrap strategies as `Opponent` interface
- **Problem**: Still uses simplified strategy functions instead of actual `DeterministicOpponent` classes

### Actual Opponent Implementations (`src/brinksmanship/opponents/deterministic.py`)
```
NashCalculator    - Risk-aware (≥8 de-escalate), 70/30 hedge when behind
SecuritySeeker    - Spiral model, risk ≥7 always cooperate, 60/40 defensive
Opportunist       - Position advantage thresholds, 60% coop when behind
Erratic           - 40/60 coop/competitive random
TitForTat         - Mirrors ActionType.COOPERATIVE/COMPETITIVE
GrimTrigger       - Uses _triggered state, never forgives
```

## Unification Design

### Core Principle
**One game runner, multiple controllers.** The game engine already supports playing a game - we just need different "controllers" for the players:
1. Human (via CLI/webapp)
2. DeterministicOpponent (actual implementations)
3. LLM Opponent (future)

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     GameEngine                              │
│  (brinksmanship/engine/game_engine.py)                     │
│  - Real state management                                    │
│  - Real delta templates                                     │
│  - Real ending conditions                                   │
│  - Real matrix types                                        │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                   GameRunner (NEW)                          │
│  (brinksmanship/testing/game_runner.py)                    │
│  - Takes two Opponent instances                             │
│  - Runs game loop using actual GameEngine                   │
│  - Handles async properly                                   │
│  - Returns structured results                               │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│              BatchRunner / PlaytestRunner                   │
│  - Runs multiple games in parallel                          │
│  - Collects statistics                                      │
│  - Uses actual DeterministicOpponent classes                │
└─────────────────────────────────────────────────────────────┘
```

### Implementation Steps

#### Step 1: Create `GameRunner` class
Location: `src/brinksmanship/testing/game_runner.py`

```python
class GameRunner:
    """Runs a single game between two opponents using the real GameEngine."""

    def __init__(
        self,
        scenario_id: str,
        opponent_a: Opponent,
        opponent_b: Opponent,
        random_seed: Optional[int] = None,
    ):
        ...

    async def run_game(self) -> GameResult:
        """Run a complete game, returning structured results."""
        engine = GameEngine(self.scenario_id, self.repo, self.random_seed)

        while not engine.is_game_over():
            state = engine.get_current_state()
            actions_a = engine.get_available_actions("A")
            actions_b = engine.get_available_actions("B")

            # Use actual opponent implementations
            action_a = await self.opponent_a.choose_action(state, actions_a)
            action_b = await self.opponent_b.choose_action(state, actions_b)

            result = engine.submit_actions(action_a, action_b)

            if result.ending:
                break

        return self._build_result(engine)
```

#### Step 2: Create `OpponentFactory`
Location: `src/brinksmanship/opponents/__init__.py`

```python
DETERMINISTIC_OPPONENTS = {
    "NashCalculator": NashCalculator,
    "SecuritySeeker": SecuritySeeker,
    "Opportunist": Opportunist,
    "Erratic": Erratic,
    "TitForTat": TitForTat,
    "GrimTrigger": GrimTrigger,
}

def create_opponent(name: str) -> Opponent:
    """Create an opponent by name."""
    if name not in DETERMINISTIC_OPPONENTS:
        raise ValueError(f"Unknown opponent: {name}")
    return DETERMINISTIC_OPPONENTS[name]()
```

#### Step 3: Create `BatchRunner` for parallel execution
Location: `src/brinksmanship/testing/batch_runner.py`

```python
class BatchRunner:
    """Runs batches of games for playtesting and balance simulation."""

    def __init__(self, scenario_id: str):
        self.scenario_id = scenario_id

    def run_pairing(
        self,
        opponent_a_name: str,
        opponent_b_name: str,
        num_games: int,
        seed: Optional[int] = None,
    ) -> PairingStats:
        """Run games between two opponent types."""
        ...

    def run_all_pairings(
        self,
        opponent_names: list[str],
        num_games: int,
    ) -> dict[str, PairingStats]:
        """Run all unique pairings."""
        ...
```

#### Step 4: Update `scripts/balance_simulation.py`
Replace current implementation to use the unified framework:

```python
from brinksmanship.testing.batch_runner import BatchRunner
from brinksmanship.opponents import DETERMINISTIC_OPPONENTS

def main():
    runner = BatchRunner(scenario_id="cuban_missile_crisis")

    results = runner.run_all_pairings(
        opponent_names=list(DETERMINISTIC_OPPONENTS.keys()),
        num_games=args.games,
    )

    print_results(results)
```

#### Step 5: Delete deprecated files
- `src/brinksmanship/testing/playtester.py` - completely superseded
- `scripts/run_playtest.py` - uses deprecated playtester

#### Step 6: Update `engine_playtester.py`
Keep the file but simplify it to use the new unified framework.

### Benefits

1. **Single source of truth** - Game mechanics defined once in `GameEngine`
2. **Actual opponent behavior** - Uses real `DeterministicOpponent` classes
3. **All matrix types** - Automatically tests all 14 matrix types from scenarios
4. **Accurate results** - Simulation matches actual gameplay
5. **Less code** - Delete ~2000 lines of duplicated logic
6. **Future-proof** - Easy to add LLM opponents

### Testing the Unified System

```bash
# Run balance simulation with actual opponents
uv run python scripts/balance_simulation.py --scenario cuban_missile_crisis --games 100

# Run specific pairing
uv run python scripts/balance_simulation.py \
    --scenario cuban_missile_crisis \
    --pairings "NashCalculator:TitForTat,Opportunist:GrimTrigger" \
    --games 500
```

### Matrix Type Coverage

The unified system will test games across all scenarios, which use different matrix types:
- `cuban_missile_crisis.json` - Chicken
- `berlin_blockade.json` - Stag Hunt
- `espionage_standoff.json` - Matching Pennies (intelligence games)
- etc.

Or we can run with a synthetic scenario that uses a specific matrix type for controlled testing.

## Files to Modify/Create

| File | Action | Description |
|------|--------|-------------|
| `src/brinksmanship/testing/game_runner.py` | CREATE | Core single-game runner |
| `src/brinksmanship/testing/batch_runner.py` | CREATE | Parallel batch execution |
| `src/brinksmanship/opponents/__init__.py` | MODIFY | Add opponent factory |
| `scripts/balance_simulation.py` | REWRITE | Use unified framework |
| `src/brinksmanship/testing/playtester.py` | DELETE | Deprecated |
| `scripts/run_playtest.py` | DELETE | Deprecated |
| `src/brinksmanship/testing/engine_playtester.py` | KEEP/SIMPLIFY | Optional wrapper |

## Estimated Impact

- **Lines deleted**: ~2000 (playtester.py + run_playtest.py + balance_simulation.py rewrite)
- **Lines added**: ~300 (game_runner.py + batch_runner.py)
- **Net reduction**: ~1700 lines
- **Correctness**: Simulations will match actual game behavior exactly
