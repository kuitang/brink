"""Playtesting framework for Brinksmanship.

This module provides automated playtesting tools for game balance validation.
All components are pure Python with no LLM orchestration - parallelism is
achieved through Python's multiprocessing.

Key classes:
- PlaytestRunner: Orchestrates batch game execution
- PairingStats: Statistics for a single strategy pairing
- PlaytestResults: Aggregate results from a full playtest run
- HumanSimulator: Simulates human player behavior for playtesting

Usage:
    from brinksmanship.testing import PlaytestRunner, HumanSimulator

    # Deterministic playtesting
    runner = PlaytestRunner()
    results = runner.run_all_pairings(games_per_pairing=100)

    # Human simulation
    simulator = HumanSimulator()
    persona = await simulator.generate_persona()
    action = await simulator.choose_action(state, actions, is_player_a=True)

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

__all__ = [
    # Core classes
    "PlaytestRunner",
    "PairingStats",
    "PlaytestResults",
    "GameResult",
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
