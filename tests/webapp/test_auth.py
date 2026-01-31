"""Tests for authentication routes."""

from brinksmanship.webapp.models import User


def test_login_page_renders(client):
    """Test login page renders."""
    response = client.get("/auth/login")
    assert response.status_code == 200
    assert b"Login" in response.data


def test_register_page_renders(client):
    """Test register page renders."""
    response = client.get("/auth/register")
    assert response.status_code == 200
    assert b"Register" in response.data


def test_register_creates_user(client, app):
    """Test user registration."""
    response = client.post(
        "/auth/register",
        data={
            "username": "newuser",
            "password": "securepass123",
            "confirm": "securepass123",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"Registration successful" in response.data

    with app.app_context():
        user = User.query.filter_by(username="newuser").first()
        assert user is not None
        assert user.check_password("securepass123")


def test_register_password_mismatch(client):
    """Test registration fails with mismatched passwords."""
    response = client.post(
        "/auth/register",
        data={
            "username": "newuser",
            "password": "securepass123",
            "confirm": "differentpass",
        },
    )
    assert response.status_code == 200
    assert b"Passwords do not match" in response.data


def test_register_short_password(client):
    """Test registration fails with short password."""
    response = client.post(
        "/auth/register",
        data={
            "username": "newuser",
            "password": "short",
            "confirm": "short",
        },
    )
    assert response.status_code == 200
    assert b"at least 8 characters" in response.data


def test_register_duplicate_username(client, user):
    """Test registration fails with duplicate username."""
    response = client.post(
        "/auth/register",
        data={
            "username": "testuser",
            "password": "securepass123",
            "confirm": "securepass123",
        },
    )
    assert response.status_code == 200
    assert b"Username already taken" in response.data


def test_login_success(client, user):
    """Test successful login."""
    response = client.post(
        "/auth/login",
        data={"username": "testuser", "password": "testpassword123"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"Your Games" in response.data  # Lobby page


def test_login_invalid_username(client, user):
    """Test login with invalid username."""
    response = client.post(
        "/auth/login",
        data={"username": "wronguser", "password": "testpassword123"},
    )
    assert response.status_code == 200
    assert b"Invalid username or password" in response.data


def test_login_invalid_password(client, user):
    """Test login with invalid password."""
    response = client.post(
        "/auth/login",
        data={"username": "testuser", "password": "wrongpassword"},
    )
    assert response.status_code == 200
    assert b"Invalid username or password" in response.data


def test_logout(auth_client):
    """Test logout."""
    response = auth_client.get("/auth/logout", follow_redirects=True)
    assert response.status_code == 200
    assert b"logged out" in response.data


def test_protected_route_redirects(client):
    """Test protected route redirects to login."""
    response = client.get("/")
    assert response.status_code == 302
    assert "/auth/login" in response.location
