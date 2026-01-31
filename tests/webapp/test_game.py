"""Tests for game routes."""

from brinksmanship.webapp.extensions import db
from brinksmanship.webapp.models import GameRecord


def create_game_record(app, user_id):
    """Helper to create a game record."""
    with app.app_context():
        record = GameRecord(
            game_id="test-game",
            user_id=user_id,
            scenario_id="cuban-missile-crisis",
            opponent_type="tit-for-tat",
        )
        record.state = {
            "scenario_id": "cuban-missile-crisis",
            "scenario_name": "Cuban Missile Crisis",
            "opponent_type": "tit-for-tat",
            "turn": 1,
            "max_turns": 14,
            "position_player": 5.0,
            "position_opponent": 5.0,
            "resources_player": 5.0,
            "resources_opponent": 5.0,
            "risk_level": 2,
            "cooperation_score": 5,
            "stability": 5,
            "last_action_player": None,
            "last_action_opponent": None,
            "history": [],
            "briefing": "Test briefing",
            "last_outcome": None,
            "is_finished": False,
            # Surplus mechanics
            "cooperation_surplus": 0.0,
            "surplus_captured_player": 0.0,
            "surplus_captured_opponent": 0.0,
            "cooperation_streak": 0,
        }
        db.session.add(record)
        db.session.commit()
        return record.id


def test_game_page_requires_login(client):
    """Test game page redirects unauthenticated users."""
    response = client.get("/game/test-game")
    assert response.status_code == 302
    assert "/auth/login" in response.location


def test_game_page_renders(auth_client, app, user):
    """Test game page renders."""
    # user is now just the user_id
    create_game_record(app, user)

    response = auth_client.get("/game/test-game")
    assert response.status_code == 200
    assert b"Cuban Missile Crisis" in response.data
    assert b"Turn 1" in response.data
    assert b"Choose Your Action" in response.data


def test_game_page_shows_status_bar(auth_client, app, user):
    """Test game page shows status bar."""
    create_game_record(app, user)

    response = auth_client.get("/game/test-game")
    assert response.status_code == 200
    assert b"Position" in response.data
    assert b"Resources" in response.data
    assert b"Risk Level" in response.data
    assert b"Cooperation" in response.data
    assert b"Stability" in response.data


def test_game_page_shows_actions(auth_client, app, user):
    """Test game page shows available actions."""
    create_game_record(app, user)

    response = auth_client.get("/game/test-game")
    assert response.status_code == 200
    # Should show action menu with cooperative and competitive options
    assert b"cooperative" in response.data or b"competitive" in response.data


def test_game_not_found(auth_client):
    """Test game not found returns 404."""
    response = auth_client.get("/game/nonexistent")
    assert response.status_code == 404


def test_submit_action(auth_client, app, user):
    """Test submitting an action."""
    create_game_record(app, user)

    response = auth_client.post(
        "/game/test-game/action",
        data={"action_id": "hold"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    # Should show turn 2 or game over
    assert b"Turn" in response.data


def test_submit_action_htmx(auth_client, app, user):
    """Test submitting an action via htmx."""
    create_game_record(app, user)

    response = auth_client.post(
        "/game/test-game/action",
        data={"action_id": "hold"},
        headers={"HX-Request": "true"},
    )
    assert response.status_code == 200
    # Should return partial HTML
    assert b"status-bar" in response.data


def test_game_over_page(auth_client, app, user):
    """Test game over page renders."""
    with app.app_context():
        record = GameRecord(
            game_id="finished-game",
            user_id=user,  # user is now the user_id directly
            scenario_id="cuban-missile-crisis",
            opponent_type="tit-for-tat",
            is_finished=True,
            ending_type="natural",
            final_vp_player=55,
            final_vp_opponent=45,
        )
        record.state = {
            "scenario_name": "Cuban Missile Crisis",
            "opponent_type": "tit-for-tat",
            "turn": 14,
            "position_player": 5.5,
            "position_opponent": 4.5,
            "resources_player": 3.0,
            "resources_opponent": 2.5,
            "risk_level": 5,
            "cooperation_score": 6,
            "stability": 7,
            "history": [{"turn": 1, "player": "C", "opponent": "C"}],
            "last_outcome": "The crisis has concluded.",
            "is_finished": True,
            # Surplus mechanics
            "cooperation_surplus": 5.0,
            "surplus_captured_player": 2.5,
            "surplus_captured_opponent": 2.5,
            "cooperation_streak": 0,
        }
        db.session.add(record)
        db.session.commit()

    response = auth_client.get("/game/finished-game/over")
    assert response.status_code == 200
    assert b"Game Over" in response.data
    assert b"55" in response.data
    assert b"45" in response.data
