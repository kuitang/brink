"""Tests for manual routes."""


def test_manual_page_loads(client):
    """Test that the manual page loads successfully."""
    response = client.get("/manual/")
    assert response.status_code == 200


def test_manual_page_has_content(client):
    """Test that the manual page has the game manual content."""
    response = client.get("/manual/")
    assert response.status_code == 200

    # Check for key sections from GAME_MANUAL.md
    assert b"Brinksmanship" in response.data
    assert b"Game Manual" in response.data


def test_manual_page_has_styling_elements(client):
    """Test that the manual page has expected styling elements."""
    response = client.get("/manual/")
    assert response.status_code == 200

    # Check for CSS class structure from manual.html template
    assert b"manual-page" in response.data
    assert b"manual-layout" in response.data
    assert b"manual-content" in response.data


def test_manual_page_has_table_of_contents(client):
    """Test that the manual page has a table of contents."""
    response = client.get("/manual/")
    assert response.status_code == 200

    # The TOC should be present with navigation links
    assert b"manual-toc" in response.data
    assert b"Contents" in response.data


def test_manual_content_has_game_theory_sections(client):
    """Test that key game theory content is present."""
    response = client.get("/manual/")
    assert response.status_code == 200

    # Check for key game theory content from GAME_MANUAL.md
    assert b"Nash Equilibrium" in response.data or b"Game Theory" in response.data
    assert b"Cooperation" in response.data
    assert b"Settlement" in response.data
