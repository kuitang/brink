"""Tests for mock game engine."""

from brinksmanship.webapp.services.mock_engine import MockGameEngine


def test_create_game():
    """Test creating a game."""
    engine = MockGameEngine()
    state = engine.create_game("cuban-missile-crisis", "tit-for-tat", 1)

    assert state["scenario_id"] == "cuban-missile-crisis"
    assert state["scenario_name"] == "Cuban Missile Crisis"
    assert state["opponent_type"] == "tit-for-tat"
    assert state["turn"] == 1
    assert state["position_player"] == 5.0
    assert state["position_opponent"] == 5.0
    assert state["resources_player"] == 5.0
    assert state["risk_level"] == 2
    assert state["cooperation_score"] == 5
    assert state["stability"] == 5
    assert state["is_finished"] is False
    assert state["history"] == []


def test_get_scenarios():
    """Test getting scenarios."""
    engine = MockGameEngine()
    scenarios = engine.get_scenarios()

    assert len(scenarios) >= 3
    assert any(s["id"] == "cuban-missile-crisis" for s in scenarios)
    assert any(s["id"] == "corporate-takeover" for s in scenarios)


def test_get_opponent_types():
    """Test getting opponent types."""
    engine = MockGameEngine()
    opponents = engine.get_opponent_types()

    assert len(opponents) >= 15  # 6 algorithmic + historical + custom
    assert any(o["id"] == "tit_for_tat" for o in opponents)
    assert any(o["id"] == "nash_calculator" for o in opponents)
    assert any(o["category"] == "algorithmic" for o in opponents)
    assert any(o["category"] == "historical_political" for o in opponents)
    assert any(o["category"] == "custom" for o in opponents)


def test_get_available_actions_low_risk():
    """Test getting actions at low risk."""
    engine = MockGameEngine()
    state = {"risk_level": 3}
    actions = engine.get_available_actions(state)

    assert len(actions) == 4
    action_ids = [a["id"] for a in actions]
    assert "deescalate" in action_ids
    assert "hold" in action_ids


def test_get_available_actions_high_risk():
    """Test getting actions at high risk."""
    engine = MockGameEngine()
    state = {"risk_level": 7}
    actions = engine.get_available_actions(state)

    assert len(actions) == 4
    action_ids = [a["id"] for a in actions]
    assert "escalate" in action_ids
    assert "ultimatum" in action_ids


def test_submit_action_updates_state():
    """Test submitting action updates state."""
    engine = MockGameEngine()
    state = engine.create_game("cuban-missile-crisis", "tit-for-tat", 1)

    new_state = engine.submit_action(state, "hold")

    assert new_state["turn"] == 2
    assert new_state["last_action_player"] == "hold"
    assert new_state["last_action_opponent"] in ["cooperate", "defect"]
    assert len(new_state["history"]) == 1
    assert new_state["last_outcome"] is not None


def test_submit_action_deducts_cost():
    """Test action cost deducted from resources."""
    engine = MockGameEngine()
    state = engine.create_game("cuban-missile-crisis", "tit-for-tat", 1)
    initial_resources = state["resources_player"]

    # Probe costs 0.5
    new_state = engine.submit_action(state, "probe")

    assert new_state["resources_player"] <= initial_resources


def test_game_ends_at_max_turns():
    """Test game ends when max turns reached."""
    engine = MockGameEngine()
    state = engine.create_game("cuban-missile-crisis", "tit-for-tat", 1)
    state["turn"] = 15  # Past max_turns of 14

    new_state = engine.submit_action(state, "hold")

    assert new_state["is_finished"] is True
    assert new_state["ending_type"] == "natural"
    assert "vp_player" in new_state
    assert "vp_opponent" in new_state


def test_game_ends_on_risk_10():
    """Test game ends on mutual destruction."""
    engine = MockGameEngine()
    state = engine.create_game("cuban-missile-crisis", "tit-for-tat", 1)
    state["risk_level"] = 9.5  # Will likely hit 10

    # Force high risk ending
    state["risk_level"] = 10

    new_state = engine.submit_action(state, "escalate")

    # Either mutual destruction or other ending
    assert new_state["is_finished"] is True


def test_history_accumulates():
    """Test history accumulates across turns."""
    engine = MockGameEngine()
    state = engine.create_game("cuban-missile-crisis", "tit-for-tat", 1)

    state = engine.submit_action(state, "hold")
    assert len(state["history"]) == 1

    state = engine.submit_action(state, "hold")
    assert len(state["history"]) == 2

    state = engine.submit_action(state, "hold")
    assert len(state["history"]) == 3
