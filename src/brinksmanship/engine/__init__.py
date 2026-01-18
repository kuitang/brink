"""Game engine module for Brinksmanship.

This module contains the core game logic including:
- variance: Variance calculation and final VP resolution
- endings: End condition checks (deterministic endings, crisis termination)
- resolution: Matrix resolution and action handling
- game_engine: Core game loop and state management

Usage:
    from brinksmanship.engine import GameEngine, create_game
    from brinksmanship.storage import get_scenario_repository

    repo = get_scenario_repository()
    game = create_game("cold-war-crisis", repo)

    # Get briefing
    print(game.get_briefing())

    # Get available actions
    actions_a = game.get_available_actions("A")
    actions_b = game.get_available_actions("B")

    # Submit actions
    result = game.submit_actions(actions_a[0], actions_b[1])

    # Check if game is over
    if game.is_game_over():
        ending = game.get_ending()
        print(f"Game over: {ending.description}")
"""

from brinksmanship.engine.game_engine import (
    EndingType,
    GameEnding,
    GameEngine,
    TurnConfiguration,
    TurnPhase,
    TurnRecord,
    TurnResult,
    create_game,
)
from brinksmanship.engine.variance import (
    calculate_base_sigma,
    calculate_chaos_factor,
    calculate_expected_vp,
    calculate_instability_factor,
    calculate_shared_sigma,
    clamp,
    final_resolution,
    get_act_multiplier,
)

__all__ = [
    # Game engine classes
    "GameEngine",
    "TurnPhase",
    "TurnRecord",
    "TurnResult",
    "TurnConfiguration",
    "GameEnding",
    "EndingType",
    "create_game",
    # Variance functions
    "calculate_base_sigma",
    "calculate_chaos_factor",
    "calculate_expected_vp",
    "calculate_instability_factor",
    "calculate_shared_sigma",
    "clamp",
    "final_resolution",
    "get_act_multiplier",
]
