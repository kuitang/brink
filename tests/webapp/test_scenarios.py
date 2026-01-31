"""Tests for scenario management routes."""


def test_scenarios_index_renders(client):
    """Test scenarios index page renders."""
    response = client.get("/scenarios/")
    assert response.status_code == 200
    assert b"Scenarios" in response.data


def test_scenarios_index_shows_scenarios(client):
    """Test scenarios index shows available scenarios."""
    response = client.get("/scenarios/")
    assert response.status_code == 200
    # Should show at least the Cuban Missile Crisis scenario
    assert b"Cuban Missile Crisis" in response.data


def test_scenario_detail_renders(client):
    """Test scenario detail page renders."""
    response = client.get("/scenarios/cuban_missile_crisis")
    assert response.status_code == 200
    assert b"Cuban Missile Crisis" in response.data
    assert b"Cold War" in response.data


def test_scenario_not_found(client):
    """Test scenario not found redirects."""
    response = client.get("/scenarios/nonexistent", follow_redirects=True)
    assert response.status_code == 200
    assert b"Scenario not found" in response.data


def test_generate_page_requires_login(client):
    """Test generate page requires authentication."""
    response = client.get("/scenarios/generate")
    assert response.status_code == 302
    assert "/auth/login" in response.location


def test_generate_page_renders(auth_client):
    """Test generate page renders for authenticated user."""
    response = auth_client.get("/scenarios/generate")
    assert response.status_code == 200
    assert b"Generate New Scenario" in response.data
    # Check themes are shown
    assert b"Cold War" in response.data
    assert b"Corporate Governance" in response.data


def test_generate_submit_shows_info(auth_client):
    """Test generate submission shows info message."""
    response = auth_client.post(
        "/scenarios/generate",
        data={"theme": "cold-war"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    # Should show info about not implemented
    assert b"not yet implemented" in response.data


def test_scenarios_public_access(client):
    """Test scenarios are accessible without login."""
    # Index should be public
    response = client.get("/scenarios/")
    assert response.status_code == 200

    # Detail should be public
    response = client.get("/scenarios/cuban_missile_crisis")
    assert response.status_code == 200
