"""Integration tests for webapp with real game engine."""

import json
import os
import pytest

from brinksmanship.webapp import create_app
from brinksmanship.webapp.config import TestConfig
from brinksmanship.webapp.extensions import db
from brinksmanship.webapp.models import User


@pytest.fixture
def test_scenario_file():
    """Create a temporary test scenario file."""
    scenario = {
        "id": "integration-test",
        "name": "Integration Test Scenario",
        "setting": "Test Setting",
        "description": "A test scenario for integration tests.",
        "max_turns": 10,
        "turns": [
            {
                "turn": 1,
                "narrative_briefing": "The integration test begins.",
                "matrix_type": "PRISONERS_DILEMMA",
            },
            {
                "turn": 2,
                "narrative_briefing": "The test continues.",
                "matrix_type": "STAG_HUNT",
            },
        ],
    }

    scenarios_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        "scenarios"
    )
    os.makedirs(scenarios_dir, exist_ok=True)

    filepath = os.path.join(scenarios_dir, "integration-test.json")
    with open(filepath, "w") as f:
        json.dump(scenario, f)

    yield "integration-test"

    if os.path.exists(filepath):
        os.remove(filepath)


@pytest.fixture
def real_engine_app(test_scenario_file):
    """Create test application with real engine."""
    app = create_app(TestConfig)
    with app.app_context():
        db.create_all()
        yield app
        db.drop_all()


@pytest.fixture
def real_engine_client(real_engine_app):
    """Create test client with real engine."""
    return real_engine_app.test_client()


@pytest.fixture
def real_engine_user(real_engine_app):
    """Create a test user."""
    with real_engine_app.app_context():
        user = User(username="realengineuser")
        user.set_password("testpassword123")
        db.session.add(user)
        db.session.commit()
        user_id = user.id
    return user_id


@pytest.fixture
def auth_real_engine_client(real_engine_client, real_engine_user):
    """Create authenticated test client with real engine."""
    real_engine_client.post(
        "/auth/login",
        data={"username": "realengineuser", "password": "testpassword123"},
    )
    return real_engine_client


def test_create_game_with_real_engine(auth_real_engine_client, test_scenario_file):
    """Test creating a game with real engine."""
    response = auth_real_engine_client.post(
        "/new",
        data={
            "scenario_id": test_scenario_file,
            "opponent_type": "tit_for_tat",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    # Should redirect to game page
    assert b"Turn" in response.data or b"turn" in response.data


def test_play_turn_with_real_engine(auth_real_engine_client, test_scenario_file):
    """Test playing a turn with real engine."""
    # Create game
    response = auth_real_engine_client.post(
        "/new",
        data={
            "scenario_id": test_scenario_file,
            "opponent_type": "security_seeker",
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    # Extract game_id from redirect URL
    location = response.headers.get("Location", "")
    game_id = location.split("/game/")[-1] if "/game/" in location else None

    assert game_id is not None

    # Get game page
    response = auth_real_engine_client.get(f"/game/{game_id}")
    assert response.status_code == 200

    # Submit an action - use "deescalate" which should be available at low risk
    response = auth_real_engine_client.post(
        f"/game/{game_id}/action",
        data={"action_id": "deescalate"},
        follow_redirects=True,
    )

    assert response.status_code == 200


def test_multiple_turns_with_real_engine(auth_real_engine_client, test_scenario_file):
    """Test playing multiple turns with real engine."""
    # Create game
    response = auth_real_engine_client.post(
        "/new",
        data={
            "scenario_id": test_scenario_file,
            "opponent_type": "erratic",
        },
        follow_redirects=False,
    )

    location = response.headers.get("Location", "")
    game_id = location.split("/game/")[-1] if "/game/" in location else None

    assert game_id is not None

    # Play 3 turns
    actions = ["hold", "pressure", "deescalate"]
    for action in actions:
        response = auth_real_engine_client.post(
            f"/game/{game_id}/action",
            data={"action_id": action},
            follow_redirects=True,
        )
        # Should either be on game page or game over page
        assert response.status_code == 200


def test_different_opponent_types(auth_real_engine_client, test_scenario_file):
    """Test creating games with different opponent types."""
    opponent_types = ["nash_calculator", "opportunist", "grim_trigger"]

    for opponent_type in opponent_types:
        response = auth_real_engine_client.post(
            "/new",
            data={
                "scenario_id": test_scenario_file,
                "opponent_type": opponent_type,
            },
            follow_redirects=True,
        )

        assert response.status_code == 200


def test_htmx_action_with_real_engine(auth_real_engine_client, test_scenario_file):
    """Test htmx action submission with real engine."""
    # Create game
    response = auth_real_engine_client.post(
        "/new",
        data={
            "scenario_id": test_scenario_file,
            "opponent_type": "tit_for_tat",
        },
        follow_redirects=False,
    )

    location = response.headers.get("Location", "")
    game_id = location.split("/game/")[-1] if "/game/" in location else None

    assert game_id is not None

    # Submit action with htmx header
    response = auth_real_engine_client.post(
        f"/game/{game_id}/action",
        data={"action_id": "hold"},
        headers={"HX-Request": "true"},
    )

    # Should return partial HTML for game board
    assert response.status_code in [200, 302]
