"""Tests for real game engine adapter."""

import json
import os
import pytest
import tempfile

from brinksmanship.webapp.services.engine_adapter import RealGameEngine


@pytest.fixture
def test_scenario_file():
    """Create a temporary test scenario file."""
    scenario = {
        "id": "test-crisis",
        "name": "Test Crisis",
        "setting": "Test Setting",
        "description": "A test scenario for unit tests.",
        "max_turns": 10,
        "turns": [
            {
                "turn": 1,
                "narrative_briefing": "The test crisis begins.",
                "matrix_type": "PRISONERS_DILEMMA",
            },
            {
                "turn": 2,
                "narrative_briefing": "The test crisis continues.",
                "matrix_type": "STAG_HUNT",
            },
        ],
    }

    # Create in scenarios directory
    scenarios_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        "scenarios"
    )
    os.makedirs(scenarios_dir, exist_ok=True)

    filepath = os.path.join(scenarios_dir, "test-crisis.json")
    with open(filepath, "w") as f:
        json.dump(scenario, f)

    yield "test-crisis"

    # Cleanup
    if os.path.exists(filepath):
        os.remove(filepath)


@pytest.fixture
def real_engine():
    """Create a real engine adapter instance."""
    return RealGameEngine()


def test_get_scenarios(real_engine):
    """Test getting scenarios from real repository."""
    scenarios = real_engine.get_scenarios()

    # Should have at least some scenarios
    assert isinstance(scenarios, list)
    # Each scenario should have expected keys
    for s in scenarios:
        assert "id" in s
        assert "name" in s


def test_get_opponent_types(real_engine):
    """Test getting opponent types."""
    opponents = real_engine.get_opponent_types()

    assert len(opponents) >= 10  # Deterministic + historical
    assert any(o["id"] == "tit_for_tat" for o in opponents)
    assert any(o["id"] == "nash_calculator" for o in opponents)
    assert any(o["id"] == "bismarck" for o in opponents)
    assert any(o["category"] == "algorithmic" for o in opponents)
    assert any(o["category"] == "custom" for o in opponents)


def test_create_game_with_deterministic_opponent(real_engine, test_scenario_file):
    """Test creating game with deterministic opponent."""
    scenario_id = test_scenario_file
    state = real_engine.create_game(scenario_id, "tit_for_tat", user_id=1)

    assert state["scenario_id"] == scenario_id
    assert state["opponent_type"] == "tit_for_tat"
    assert state["turn"] == 1
    assert "position_player" in state
    assert "resources_player" in state
    assert "risk_level" in state
    assert state["is_finished"] is False
    assert "game_id" in state


def test_get_available_actions(real_engine, test_scenario_file):
    """Test getting available actions for a game."""
    scenario_id = test_scenario_file
    state = real_engine.create_game(scenario_id, "security_seeker", user_id=2)

    actions = real_engine.get_available_actions(state)

    assert len(actions) >= 2
    # Should have both cooperative and competitive actions
    types = [a["type"] for a in actions]
    assert "cooperative" in types
    assert "competitive" in types


def test_submit_action_updates_state(real_engine, test_scenario_file):
    """Test submitting an action updates the game state."""
    scenario_id = test_scenario_file
    state = real_engine.create_game(scenario_id, "tit_for_tat", user_id=3)

    actions = real_engine.get_available_actions(state)
    if not actions:
        pytest.skip("No actions available")

    # Submit first available action
    action_id = actions[0]["id"]
    new_state = real_engine.submit_action(state, action_id)

    assert new_state["turn"] >= 1  # Turn should advance or stay same if game ended
    assert new_state["last_action_player"] is not None
    assert new_state["last_action_opponent"] in ["cooperate", "defect"]
    assert len(new_state["history"]) == 1


def test_game_flow(real_engine, test_scenario_file):
    """Test playing multiple turns."""
    scenario_id = test_scenario_file
    state = real_engine.create_game(scenario_id, "erratic", user_id=4)

    turns_played = 0
    max_turns = 5  # Play up to 5 turns

    while not state.get("is_finished") and turns_played < max_turns:
        actions = real_engine.get_available_actions(state)
        if not actions:
            break

        # Alternate between cooperative and competitive
        if turns_played % 2 == 0:
            action = next((a for a in actions if a["type"] == "cooperative"), actions[0])
        else:
            action = next((a for a in actions if a["type"] == "competitive"), actions[0])

        state = real_engine.submit_action(state, action["id"])
        turns_played += 1

    assert turns_played > 0
    assert len(state["history"]) == turns_played
