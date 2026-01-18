"""Tests for leaderboard routes and service."""

from datetime import datetime

from brinksmanship.webapp.extensions import db
from brinksmanship.webapp.models import GameRecord, User
from brinksmanship.webapp.services.leaderboard import (
    get_available_leaderboards,
    get_leaderboard,
)


def create_finished_game(app, user_id, scenario_id, opponent_type, vp, turn=10):
    """Helper to create a finished game record."""
    with app.app_context():
        game = GameRecord(
            game_id=f"game-{user_id}-{scenario_id}-{vp}",
            user_id=user_id,
            scenario_id=scenario_id,
            opponent_type=opponent_type,
            is_finished=True,
            ending_type="natural",
            final_vp_player=vp,
            final_vp_opponent=100 - vp,
            finished_at=datetime.utcnow(),
        )
        game.state = {
            "scenario_name": scenario_id.replace("-", " ").title(),
            "opponent_type": opponent_type,
            "turn": turn,
        }
        db.session.add(game)
        db.session.commit()
        return game.id


def test_leaderboards_index_renders(client, app):
    """Test leaderboards index page renders."""
    response = client.get("/leaderboard/")
    assert response.status_code == 200
    assert b"Leaderboards" in response.data


def test_leaderboards_index_empty(client, app):
    """Test leaderboards index with no games."""
    response = client.get("/leaderboard/")
    assert response.status_code == 200
    assert b"No completed games yet" in response.data


def test_leaderboards_index_shows_games(client, app, user):
    """Test leaderboards index shows completed games."""
    create_finished_game(app, user, "cuban-missile-crisis", "tit-for-tat", 60)

    response = client.get("/leaderboard/")
    assert response.status_code == 200
    assert b"Cuban Missile Crisis" in response.data
    assert b"tit-for-tat" in response.data


def test_leaderboard_view_renders(client, app, user):
    """Test individual leaderboard page renders."""
    create_finished_game(app, user, "cuban-missile-crisis", "tit-for-tat", 60)

    response = client.get("/leaderboard/cuban-missile-crisis/tit-for-tat")
    assert response.status_code == 200
    assert b"60" in response.data


def test_leaderboard_view_empty(client, app):
    """Test leaderboard view with no games."""
    response = client.get("/leaderboard/cuban-missile-crisis/tit-for-tat")
    assert response.status_code == 200
    assert b"No games completed" in response.data


def test_leaderboard_ranking(app, user):
    """Test leaderboard ranking order."""
    # Create another user
    with app.app_context():
        user2 = User(username="player2")
        user2.set_password("password123")
        db.session.add(user2)
        db.session.commit()
        user2_id = user2.id

    # Create games with different scores
    create_finished_game(app, user, "cuban-missile-crisis", "tit-for-tat", 50)
    create_finished_game(app, user2_id, "cuban-missile-crisis", "tit-for-tat", 70)

    with app.app_context():
        entries = get_leaderboard("cuban-missile-crisis", "tit-for-tat")

    assert len(entries) == 2
    # Higher VP should be first
    assert entries[0]["vp"] == 70
    assert entries[0]["rank"] == 1
    assert entries[1]["vp"] == 50
    assert entries[1]["rank"] == 2


def test_leaderboard_highlights_current_user(auth_client, app, user):
    """Test current user is highlighted in leaderboard."""
    create_finished_game(app, user, "cuban-missile-crisis", "tit-for-tat", 55)

    response = auth_client.get("/leaderboard/cuban-missile-crisis/tit-for-tat")
    assert response.status_code == 200
    # User should be highlighted
    assert b"(you)" in response.data


def test_available_leaderboards(app, user):
    """Test get_available_leaderboards returns correct data."""
    create_finished_game(app, user, "cuban-missile-crisis", "tit-for-tat", 60)
    create_finished_game(app, user, "cuban-missile-crisis", "tit-for-tat", 55)
    create_finished_game(app, user, "corporate-takeover", "nash", 70)

    with app.app_context():
        leaderboards = get_available_leaderboards()

    assert len(leaderboards) == 2

    # Find the Cuban Missile Crisis leaderboard
    cmc = next(lb for lb in leaderboards if lb["scenario_id"] == "cuban-missile-crisis")
    assert cmc["opponent_type"] == "tit-for-tat"
    assert cmc["game_count"] == 2

    # Find the Corporate Takeover leaderboard
    ct = next(lb for lb in leaderboards if lb["scenario_id"] == "corporate-takeover")
    assert ct["opponent_type"] == "nash"
    assert ct["game_count"] == 1


def test_leaderboard_public_access(client, app, user):
    """Test leaderboard is accessible without login."""
    create_finished_game(app, user, "cuban-missile-crisis", "tit-for-tat", 60)

    # Index should be public
    response = client.get("/leaderboard/")
    assert response.status_code == 200

    # Individual leaderboard should be public
    response = client.get("/leaderboard/cuban-missile-crisis/tit-for-tat")
    assert response.status_code == 200
