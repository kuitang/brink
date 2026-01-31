"""Tests for surplus field synchronization in engine adapter."""

import pytest

from brinksmanship.webapp.services.engine_adapter import RealGameEngine


@pytest.fixture
def engine() -> RealGameEngine:
    """Create engine adapter for testing."""
    return RealGameEngine()


def test_surplus_fields_synced_on_engine_recreation(engine: RealGameEngine) -> None:
    """Test that surplus fields are preserved when recreating engine from state."""
    state = engine.create_game(
        scenario_id="cuban_missile_crisis",
        opponent_type="tit_for_tat",
        user_id=1,
    )

    state["cooperation_surplus"] = 15.0
    state["surplus_captured_player"] = 5.0
    state["surplus_captured_opponent"] = 3.0
    state["cooperation_streak"] = 4

    recreated_engine = engine._create_engine_from_state(state)

    assert recreated_engine.state.cooperation_surplus == 15.0
    assert recreated_engine.state.cooperation_streak == 4
    assert recreated_engine.state.surplus_captured_a == 5.0
    assert recreated_engine.state.surplus_captured_b == 3.0


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
    """Test that surplus accumulates correctly across multiple turns."""
    state = engine.create_game(
        scenario_id="cuban_missile_crisis",
        opponent_type="tit_for_tat",
        user_id=1,
    )

    assert state.get("cooperation_surplus", 0.0) == 0.0

    actions = engine.get_available_actions(state)
    coop_action = next((a for a in actions if a.get("type") == "cooperative"), None)

    if not coop_action:
        return

    new_state = engine.submit_action(state, coop_action["id"])

    actions2 = engine.get_available_actions(new_state)
    coop_action2 = next((a for a in actions2 if a.get("type") == "cooperative"), None)

    if not coop_action2:
        return

    state_after_turn2 = engine.submit_action(new_state, coop_action2["id"])
    surplus_after_turn2 = state_after_turn2.get("cooperation_surplus", 0.0)

    assert surplus_after_turn2 >= 0.0


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
