"""Tests for lobby routes."""


def test_lobby_requires_login(client):
    """Test lobby redirects unauthenticated users."""
    response = client.get("/")
    assert response.status_code == 302
    assert "/auth/login" in response.location


def test_lobby_renders(auth_client):
    """Test lobby page renders for authenticated user."""
    response = auth_client.get("/")
    assert response.status_code == 200
    assert b"Your Games" in response.data
    assert b"Active Games" in response.data
    assert b"Recent Completed Games" in response.data


def test_new_game_page_renders(auth_client):
    """Test new game page renders."""
    response = auth_client.get("/new")
    assert response.status_code == 200
    assert b"Start New Game" in response.data
    assert b"Scenario" in response.data
    assert b"Opponent" in response.data


def test_new_game_page_shows_scenarios(auth_client):
    """Test new game page shows available scenarios."""
    response = auth_client.get("/new")
    assert response.status_code == 200
    assert b"Cuban Missile Crisis" in response.data
    assert b"Hostile Takeover" in response.data


def test_new_game_page_shows_opponents(auth_client):
    """Test new game page shows available opponents."""
    response = auth_client.get("/new")
    assert response.status_code == 200
    assert b"Tit-for-Tat" in response.data
    assert b"Nash Equilibrium" in response.data
    assert b"Bismarck" in response.data


def test_create_game(auth_client, app):
    """Test creating a new game."""
    response = auth_client.post(
        "/new",
        data={
            "scenario_id": "cuban-missile-crisis",
            "opponent_type": "tit-for-tat",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    # Should be on game page
    assert b"Cuban Missile Crisis" in response.data
    assert b"Turn 1" in response.data


def test_create_game_missing_fields(auth_client):
    """Test creating game with missing fields."""
    response = auth_client.post(
        "/new",
        data={"scenario_id": "", "opponent_type": ""},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"Please select a scenario and opponent" in response.data
