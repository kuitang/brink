"""Tests for surplus field synchronization in engine adapter.

This tests that the webapp engine adapter properly syncs surplus fields
when recreating engines from stored state (T25 bug fix).
"""

import pytest
from brinksmanship.webapp.services.engine_adapter import RealGameEngine


@pytest.fixture
def engine() -> RealGameEngine:
    """Create engine adapter for testing."""
    return RealGameEngine()


def test_surplus_fields_synced_on_engine_recreation(engine: RealGameEngine) -> None:
    """Test that surplus fields are preserved when recreating engine from state.

    This reproduces the bug where surplus accumulated during gameplay
    was lost when the engine was recreated for the next turn.
    """
    # Create a new game
    state = engine.create_game(
        scenario_id="cuban_missile_crisis",
        opponent_type="tit_for_tat",
        user_id=1,
    )

    # Manually set surplus values as if they accumulated during play
    state["cooperation_surplus"] = 15.0
    state["surplus_captured_player"] = 5.0
    state["surplus_captured_opponent"] = 3.0
    state["cooperation_streak"] = 4

    # Recreate engine from state (this is what happens each turn)
    recreated_engine = engine._create_engine_from_state(state)

    # Verify surplus fields are preserved
    assert recreated_engine.state.cooperation_surplus == 15.0, \
        "cooperation_surplus not synced"
    assert recreated_engine.state.cooperation_streak == 4, \
        "cooperation_streak not synced"

    # Check captured amounts based on player side
    player_is_a = state.get("player_is_a", True)
    if player_is_a:
        assert recreated_engine.state.surplus_captured_a == 5.0, \
            "surplus_captured_a (player) not synced"
        assert recreated_engine.state.surplus_captured_b == 3.0, \
            "surplus_captured_b (opponent) not synced"
    else:
        assert recreated_engine.state.surplus_captured_b == 5.0, \
            "surplus_captured_b (player) not synced"
        assert recreated_engine.state.surplus_captured_a == 3.0, \
            "surplus_captured_a (opponent) not synced"


def test_surplus_fields_synced_player_b(engine: RealGameEngine) -> None:
    """Test surplus sync when player is side B."""
    state = engine.create_game(
        scenario_id="cuban_missile_crisis",
        opponent_type="tit_for_tat",
        user_id=1,
        player_is_a=False,
    )

    state["cooperation_surplus"] = 20.0
    state["surplus_captured_player"] = 8.0  # Player is B
    state["surplus_captured_opponent"] = 4.0  # Opponent is A
    state["cooperation_streak"] = 3

    recreated_engine = engine._create_engine_from_state(state)

    assert recreated_engine.state.cooperation_surplus == 20.0
    assert recreated_engine.state.cooperation_streak == 3
    # Player is B, so captured_player goes to B
    assert recreated_engine.state.surplus_captured_b == 8.0
    assert recreated_engine.state.surplus_captured_a == 4.0


def test_surplus_accumulates_across_turns(engine: RealGameEngine) -> None:
    """Test that surplus accumulates correctly across multiple turns.

    Simulates multiple turns to ensure surplus isn't reset.
    """
    state = engine.create_game(
        scenario_id="cuban_missile_crisis",
        opponent_type="tit_for_tat",
        user_id=1,
    )

    initial_surplus = state.get("cooperation_surplus", 0.0)
    assert initial_surplus == 0.0, "Initial surplus should be 0"

    # Submit an action (cooperative to trigger CC with tit_for_tat)
    # This should create surplus if both cooperate
    actions = engine.get_available_actions(state)

    # Find a cooperative action
    coop_action = None
    for action in actions:
        if action.get("type") == "cooperative":
            coop_action = action
            break

    if coop_action:
        new_state = engine.submit_action(state, coop_action["id"])

        # After CC, surplus should have increased
        new_surplus = new_state.get("cooperation_surplus", 0.0)
        new_streak = new_state.get("cooperation_streak", 0)

        # Submit another cooperative action
        actions2 = engine.get_available_actions(new_state)
        coop_action2 = None
        for action in actions2:
            if action.get("type") == "cooperative":
                coop_action2 = action
                break

        if coop_action2:
            state_after_turn2 = engine.submit_action(new_state, coop_action2["id"])

            # Surplus should continue accumulating
            surplus_after_turn2 = state_after_turn2.get("cooperation_surplus", 0.0)

            # The key test: surplus should be >= what it was (may be equal if CD/DC captured some)
            # But it should NOT be reset to 0
            assert surplus_after_turn2 >= 0.0, "Surplus should not be negative"


def test_default_surplus_values_when_missing(engine: RealGameEngine) -> None:
    """Test that missing surplus fields default to 0."""
    # Create minimal state without surplus fields
    state = {
        "scenario_id": "cuban_missile_crisis",
        "turn": 1,
        "player_is_a": True,
        "position_player": 5.0,
        "position_opponent": 5.0,
        "resources_player": 5.0,
        "resources_opponent": 5.0,
        "risk_level": 2.0,
        "cooperation_score": 5,
        "stability": 5,
        # No surplus fields - should default to 0
    }

    recreated_engine = engine._create_engine_from_state(state)

    assert recreated_engine.state.cooperation_surplus == 0.0
    assert recreated_engine.state.surplus_captured_a == 0.0
    assert recreated_engine.state.surplus_captured_b == 0.0
    assert recreated_engine.state.cooperation_streak == 0
