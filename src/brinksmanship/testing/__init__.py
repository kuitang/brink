"""Playtesting framework for Brinksmanship.

This module provides automated playtesting tools for game balance validation.
All components use the ACTUAL opponent implementations from
brinksmanship.opponents.deterministic to ensure simulation matches real gameplay.

Key classes:
- GameRunner: Runs single games using real GameEngine and Opponent instances
- BatchRunner: Orchestrates parallel batch execution for balance testing
- HumanSimulator: Simulates human player behavior for playtesting

Usage:
    from brinksmanship.testing import GameRunner, BatchRunner
    from brinksmanship.opponents.deterministic import TitForTat, NashCalculator

    # Run a single game
    result = run_game_sync(
        scenario_id="cuban_missile_crisis",
        opponent_a=TitForTat(),
        opponent_b=NashCalculator(),
    )

    # Run batch simulations
    runner = BatchRunner(scenario_id="cuban_missile_crisis")
    results = runner.run_all_pairings(num_games=100)

    # Human simulation
    simulator = HumanSimulator()
    persona = await simulator.generate_persona()
    action = simulator.choose_action(state, actions)

See ENGINEERING_DESIGN.md Milestones 5.1 and 5.2 for specifications.
"""

from .batch_runner import (
    ALL_OPPONENTS,
    DETERMINISTIC_OPPONENTS,
    BatchResults,
    BatchRunner,
    PairingStats,
    create_opponent,
    print_results_summary,
)
from .game_runner import (
    GameResult,
    GameRunner,
    run_game_sync,
)
from .human_simulator import (
    # Response models
    ActionSelection,
    HumanPersona,
    # Core classes
    HumanSimulator,
    MistakeCheck,
    SettlementResponse,
)

__all__ = [
    # Game Runner (single games)
    "GameRunner",
    "GameResult",
    "run_game_sync",
    # Batch Runner (parallel simulations)
    "BatchRunner",
    "PairingStats",
    "BatchResults",
    "DETERMINISTIC_OPPONENTS",
    "ALL_OPPONENTS",
    "create_opponent",
    "print_results_summary",
    # Human Simulator
    "HumanSimulator",
    "HumanPersona",
    "ActionSelection",
    "MistakeCheck",
    "SettlementResponse",
]
