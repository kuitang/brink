"""Playtesting framework for Brinksmanship.

This module provides automated playtesting tools for game balance validation.
All components are pure Python with no LLM orchestration - parallelism is
achieved through Python's multiprocessing.

Key classes:
- PlaytestRunner: Orchestrates batch game execution (simplified simulation)
- EnginePlaytestRunner: Uses real GameEngine with scenario loading
- PairingStats: Statistics for a single strategy pairing
- PlaytestResults: Aggregate results from a full playtest run
- HumanSimulator: Simulates human player behavior for playtesting

Usage:
    from brinksmanship.testing import PlaytestRunner, HumanSimulator

    # Deterministic playtesting (simplified simulation)
    runner = PlaytestRunner()
    results = runner.run_all_pairings(games_per_pairing=100)

    # Engine-based playtesting with scenario
    from brinksmanship.testing import EnginePlaytestRunner
    runner = EnginePlaytestRunner("cuban-missile-crisis")
    results = runner.run_all_pairings(games_per_pairing=100)

    # Human simulation
    simulator = HumanSimulator()
    persona = await simulator.generate_persona()
    action = simulator.choose_action(state, actions)

See ENGINEERING_DESIGN.md Milestones 5.1 and 5.2 for specifications.
"""

from .playtester import (
    # Core classes
    PlaytestRunner,
    PairingStats,
    PlaytestResults,
    GameResult,
    # State classes
    SimpleGameState,
    SimplePlayerState,
    # Enums
    ActionChoice,
    EndingType,
    # Strategy type alias
    Strategy,
    # Built-in strategies
    STRATEGIES,
    tit_for_tat,
    always_defect,
    always_cooperate,
    opportunist,
    nash_equilibrium,
    grim_trigger,
    random_strategy,
    # Game execution
    run_game,
    run_pairing_batch,
    # Utilities
    print_results_summary,
)

from .human_simulator import (
    # Core classes
    HumanSimulator,
    HumanPersona,
    # Response models
    ActionSelection,
    MistakeCheck,
    SettlementResponse,
)

from .engine_playtester import (
    # Core classes
    EnginePlaytestRunner,
    EngineGameResult,
    EnginePairingStats,
    EnginePlaytestResults,
    # Adapter
    StrategyAdapter,
    # Strategy type alias
    EngineStrategy,
    # Built-in engine strategies
    ENGINE_STRATEGIES,
    engine_tit_for_tat,
    engine_always_cooperate,
    engine_always_defect,
    engine_opportunist,
    engine_nash,
    engine_random,
    # Game execution
    run_engine_game,
)

__all__ = [
    # Core classes (simplified playtester)
    "PlaytestRunner",
    "PairingStats",
    "PlaytestResults",
    "GameResult",
    # Engine-integrated playtester
    "EnginePlaytestRunner",
    "EngineGameResult",
    "EnginePairingStats",
    "EnginePlaytestResults",
    "StrategyAdapter",
    "EngineStrategy",
    "ENGINE_STRATEGIES",
    "engine_tit_for_tat",
    "engine_always_cooperate",
    "engine_always_defect",
    "engine_opportunist",
    "engine_nash",
    "engine_random",
    "run_engine_game",
    # Human Simulator
    "HumanSimulator",
    "HumanPersona",
    "ActionSelection",
    "MistakeCheck",
    "SettlementResponse",
    # State classes
    "SimpleGameState",
    "SimplePlayerState",
    # Enums
    "ActionChoice",
    "EndingType",
    # Strategy type alias
    "Strategy",
    # Built-in strategies
    "STRATEGIES",
    "tit_for_tat",
    "always_defect",
    "always_cooperate",
    "opportunist",
    "nash_equilibrium",
    "grim_trigger",
    "random_strategy",
    # Game execution
    "run_game",
    "run_pairing_batch",
    # Utilities
    "print_results_summary",
]
